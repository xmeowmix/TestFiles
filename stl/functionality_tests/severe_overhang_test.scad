scale([2,2,2])
rotate([90,0,0]){
union(){
difference(){
cylinder(r=10,h=5,center=true);
translate([0,-3,0])
scale([1.3,1,1])
cylinder(r=10,h=10,center=true);
}
translate([0,5,0])
cube([5,10,5],center=true);
}
}