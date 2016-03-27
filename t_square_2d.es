set maxdepth 100
R1
R2
rule R1 md 5 {
{ s 1 1 0.1} grid
{x 0.5 y 0.5 s 0.5 0.5 1 rz 90} R1
{x  -0.5 y -0.5 s 0.5 0.5 1 rz -90} R1
{x 0.5 y -0.5 s 0.5 0.5 1} R1
}

rule R2 md 4 {
{x -0.5 y 0.5 s 0.5 0.5 1 rz 180} R1
}