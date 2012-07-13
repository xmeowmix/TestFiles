#!/usr/bin/python

import os
import sys
import re
import pysvg.structure
import pysvg.shape
import pysvg.builders
import pysvg.text
from math import sqrt


gcode_file = ''
dump_dir = './'
factor = 10
extruder_mode = 1

svg_dir = 'svg/'

extrude_style = pysvg.builders.StyleBuilder()
extrude_style.setStrokeWidth(.2 * factor)
extrude_style.setStroke('red')

move_style = pysvg.builders.StyleBuilder()
move_style.setStrokeWidth(.2 * factor)
move_style.setStroke('blue')

layer_begin = re.compile('^\((<layer>|Slice) [\d.]+.*\)$')

def layer_filename(layer_num):
    return dump_dir+svg_dir+'layer_'+str(layer_num)+'.svg'

class Coord(object):
    def __init__(self, x=0.0, y=0.0, z=0.0, copy = None):
        if copy is None:
            self.x = x
            self.y = y
            self.z = z
        else:
            self.x = copy.x
            self.y = copy.y
            self.z = copy.z
    def copy(self, other):
        self.x = other.x
        self.y = other.y
        self.z = other.z
    def __abs__(self):
        return sqrt(self.x**2 + self.y**2 + self.z**2)
    def __sub__(self, other):
        return Coord(self.x - other.x, self.y - other.y, self.z - other.z)
    def __repr__(self):
        return "(" + repr(self.x) + ", " + repr(self.y) + ", " + repr(self.z) + ")"
    def __str__(self):
        return "(" + str(self.x) + ", " + str(self.y) + ", " + str(self.z) + ")"

def distance_linear(coord1, coord2):
    return abs(coord2 - coord1)

#represents the lowest coordinates, used when outputting to svg
minposition = Coord()

class Gantry(object):
    def __init__(self):
        self.position = Coord()
        self.A = 0.0
        self.B = 0.0
        self.E = 0.0
        self.isExtruding = False
        #how much movement while extruding with A
        self.AdistanceAccum = 0.0
        #how much movement while extruding with B
        self.BdistanceAccum = 0.0
        #how much movement while extruding with E
        self.EdistanceAccum = 0.0
        #how much movement without extruding
        self.DryAccum = 0.0
        #how many times we retracted
        self.RetractAccum = 0
        #how many times we switched any extruder on
        self.SwitchAccum = 0
        #how long are we moving on this layer
        self.DurationAccum = 0.0
    def flush_accumulators(self, svg_object):
        '''Output accumulator values to svg and reset them.
        '''
        table = "<g transform='translate(32, 32)'>\n"
        tablec = "</g>\n"
        
        def tr(y):
            return "\t<text font-family='monospace' transform='translate(0," + str(y) + ")'>\n"
        
        trc = "\t</text>\n"
        def td(x):
            return "\t\t<tspan x='" + str(x) + "'>\n\t\t"
        tdc = "\t\t</tspan>\n"
        htmltable =     [["Sum of Distance : ", str(self.AdistanceAccum +
                                                  self.BdistanceAccum +
                                                  self.EdistanceAccum +
                                                  self.DryAccum), "(mm)"],
                         ["Ext. A Distance : ", str(self.AdistanceAccum), "(mm)"],
                         ["Ext. B Distance : ", str(self.BdistanceAccum), "(mm)"],
                         ["Ext. E Distance : ", str(self.EdistanceAccum), "(mm)"],
                         ["Moving Distance : ", str(self.DryAccum), "(mm)"],
                         ["Travel Duration : ", str(self.DurationAccum), "(sec)"],
                         ["Extruder Toggle : ", str(self.SwitchAccum), "(count)"],
                         ["Retractions Num : ", str(self.RetractAccum), "(count)"]]
        y = 0
        htmlstring = table
        for row in htmltable:
            htmlstring += tr(y)
            y+=18
            x = 0
            for col in row:
                htmlstring += td(x)
                x += 150
                htmlstring += col
                htmlstring += "\n"
                htmlstring += tdc
            htmlstring += trc
        htmlstring += tablec
        svg_object.appendTextContent(htmlstring)
        self.isExtruding = False
        self.AdistanceAccum = 0.0
        self.BdistanceAccum = 0.0
        self.EdistanceAccum = 0.0
        self.DryAccum = 0.0
        self.RetractAccum = 0
        self.SwitchAccum = 0
        self.DurationAccum = 0.0
        
    def process_splitcode(self, position, A, B, E, F, Layer, svg_object):
        '''Process new position and extrusion axes.
        '''
        retbool = False
        extrudebool = False
        retractbool = False
        startpos = self.position - minposition
        endpos = position - minposition
        myline = pysvg.shape.line(startpos.x * factor, startpos.y * factor,
                      endpos.x * factor, endpos.y * factor)
        distance = distance_linear(position, self.position)
        filament_distance = abs(A - self.A) + abs(B-self.B) + abs(E-self.E)
        if F is not None:
            self.DurationAccum += (filament_distance) / (F / 60)
            self.DurationAccum += (distance) / (F / 60)
        #increment appropriate values
        if A != self.A:
            extrudebool = True
            retractbool = retractbool or A < self.A
            self.AdistanceAccum += distance
        if B != self.B:
            extrudebool = True
            retractbool = retractbool or B < self.B
            self.BdistanceAccum += distance
        if E != self.E:
            extrudebool = True
            retractbool = retractbool or E < self.E
            self.EdistanceAccum += distance
        if extrudebool != self.isExtruding:
            self.isExtruding = extrudebool
            self.SwitchAccum += 1
        if retractbool:
            self.RetractAccum += 1
            mycircle = pysvg.shape.circle(endpos.x * factor, endpos.y * factor, 0.3125 * factor)
            svg_object.addElement(mycircle)
        if Layer:
            retbool = True
        elif extrudebool:
            #emit an extrusion move
            myline.set_style(extrude_style.getStyle())
            svg_object.addElement(myline)
        elif position.x != self.position.x or position.y != self.position.y:
            #emit a nonextudsion move and update dry distance
            myline.set_style(move_style.getStyle())
            svg_object.addElement(myline)
            self.DryAccum += distance
        if retbool:
            self.flush_accumulators(svg_object)
        self.position = position
        self.A = A
        self.B = B
        self.E = E
        return retbool
    def process_code(self, gcode_dict, svg_object):
        '''Process one line of gcode.
        
        Process the gcode and emit the appropriate line to the svg file. If
        not layer change, return false. Otherwise return true.
        '''
        position = Coord(copy = self.position)
        A = self.A
        B = self.B
        E = self.E
        F = None
        Layer = None
        if 'X' in gcode_dict:
            position.x = gcode_dict['X']
        if 'Y' in gcode_dict:
            position.y = gcode_dict['Y']
        if 'Z' in gcode_dict:
            position.z = gcode_dict['Z']
        if 'A' in gcode_dict:
            A = gcode_dict['A']
        if 'B' in gcode_dict:
            B = gcode_dict['B']
        if 'E' in gcode_dict:
            E = gcode_dict['E']
        if 'F' in gcode_dict:
            F = gcode_dict['F']
        if 'Layer' in gcode_dict:
            Layer = gcode_dict['Layer']
        return Gantry.process_splitcode(self, position, A, B, E, F, Layer, svg_object)
        

def code_dict_from_line(gcode_line):
    retDict = dict()
    gl = gcode_line.split()
    for word in gl:
        if len(word) < 2 or word[0] not in 'ABEFGMXYZ':
            break
        retDict[word[0]] = float(word[1:])
    match = layer_begin.match(gcode_line)
    if match is not None:
        retDict['Layer'] = True
    return retDict

def make_html(svgList, title):
    if title is None:
        print "Current file name is not valid"
        return
    htmlname = dump_dir + 'index.html'
    print "Outputting index.html to " + htmlname
    print "Base directory is " + dump_dir
    fh = open(dump_dir + 'index.html', "w")
    fh.write("<html>\n")
    #head
    fh.write("\t<head>\n")
    fh.write("\t\t<title>" + title + "</title>\n");
    fh.write("\t</head>\n")
    #end head
    #body
    fh.write("\t<body>\n")
    #table
    fh.write("\t\t<table>\n")
    for svg in svgList:
        svgmod = svg[svg.find(dump_dir) + len(dump_dir):]
        #print "Indexing: \t" + svgmod
        fh.write("\t\t\t<tr>\n")
        #file name
        fh.write("\t\t\t\t<td>")
        fh.write("<a href = \"" + svgmod + "\">")
        fh.write(svgmod)
        fh.write("</a>")
        fh.write("</td>\n")
        #preview
        fh.write("\t\t\t\t<td>")
        #fh.write("<a href = \"" + svg + "\">")
        #fh.write("<object height=\"32\" width=\"48\" type=\"image/svg+xml\" data = \"" + svgmod + "\" >")
        #fh.write(svg)
        #fh.write(" alt text</object>")
        #fh.write("</a>")
        fh.write("</td>\n")
        fh.write("\t\t\t</tr>\n")
    fh.write("\t\t</table>\n")
    #end table
    fh.write("\t</body>\n")
    #end body
    fh.write("</html>\n")
    fh.close()

################################################################################

def main(argv=None):
    
    if argv is None:
        argv = sys.argv
        
    lsa = len(argv)
    print "slice_analyzer: ", lsa, " arguments\n";

    global gcode_file
    global dump_dir
    global factor
    global extuder_mode
    
    for arg in range(0, lsa):
        print "#", arg, ": \t", argv[arg];

    if lsa < 2:
        print """

    Slice analyzer
    Usage: 
        slice_analyzer.py GCODE_FILE [OUTPUT_DIRECTORY] [SCALE_FACTOR] [EXTRUDER_MODE]
        
        where:
            GCODE_FILE       : the input file to analyze
            OUTPUT_DIRECTORY : the directory where all text and svg files are stored
            SCALE_FACTOR     : SVG scale factor (10 recommended)
            EXTRUDER_MODE    : not used? (integer)
    """
        return -1
    if lsa >= 2:
        gcode_file = argv[1];
    if lsa >= 3:
        dump_dir = argv[2];
        if dump_dir == '':
            dump_dir = './'
        elif dump_dir[-1] != '/':
            dump_dir = dump_dir + '/'
    if lsa >= 4:
        factor = int(argv[3]);
    if lsa >= 5:
        extruder_mode = int(argv[4]);

    if not os.path.exists(dump_dir+svg_dir):
        os.makedirs(dump_dir+svg_dir)

    print "Input File: \t" + str(gcode_file)
    print "Output Directory: \t" + str(dump_dir)
    print "Scaling Factor: \t" + str(factor)

    if not os.path.exists(dump_dir):
        os.makedirs(dump_dir)
    if not os.path.exists(dump_dir + svg_dir):
        os.makedirs(dump_dir + svg_dir)

    gcode_fh = open(gcode_file, "r")
    svgList = []

    #find the bounds of the object
    for gcode_line in gcode_fh.readlines():
        gcode_line = gcode_line.rstrip()
        code_dict = code_dict_from_line(gcode_line)
        if 'X' in code_dict:
            minposition.x = min([minposition.x, code_dict['X']])
        if 'Y' in code_dict:
            minposition.y = min([minposition.y, code_dict['Y']])


    print "Minimum Coordinates: \t" + str(minposition)

    gcode_fh.close()
    gcode_fh = open(gcode_file, "r")

    gantry = Gantry()
    layer_num = 0

    svg_filename = layer_filename(layer_num)
    svg_object = pysvg.structure.svg("Layer " + str(layer_num))

    print "Starting processing of layers"

    for gcode_line in gcode_fh.readlines():
        gcode_line = gcode_line.strip()
        if gantry.process_code(code_dict_from_line(gcode_line),svg_object):
            svg_object.save(svg_filename)
            svgList.append(svg_filename)
            sys.stdout.write('.')
            layer_num += 1
            svg_filename = layer_filename(layer_num)
            svg_object = pysvg.structure.svg("Layer " + str(layer_num))
    gantry.flush_accumulators(svg_object)
    svg_object.save(svg_filename)
    svgList.append(svg_filename)

    print ""

    print "Layers: \t" + str(layer_num)
    print "Starting generation of index"

    make_html(svgList, gcode_file)
    return 0

if __name__ == "__main__":
    sys.exit(main())
        




