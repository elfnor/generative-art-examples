set maxdepth 100
{y  0.866 } R1
{rz 120 y 0.866} R1
{rz 240 y 0.866} R1

rule R1  md 4 > unit {
{x -1 s 0.333} R1
{x -0.25 y 0.433 rz 60 s 0.333} R1
{x 0.25 y 0.433 rz -60 s 0.333} R1
{x 1 s 0.333} R1
}

rule unit {
{s 3} line
}