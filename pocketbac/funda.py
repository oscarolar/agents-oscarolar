import manifold3d as m, trimesh, numpy as np, sys
out = sys.argv[1]
def rrect(w, d, r, h, z=0):
    cs = m.CrossSection.square([w-2*r, d-2*r], center=True).offset(r, m.JoinType.Round, circular_segments=64)
    return m.Manifold.extrude(cs, h).translate([0,0,z])
# Botella: 41.5 x 24.3 ; holgura PETG 0.85 mm por lado
CW, CD, CR = 43.2, 26.0, 8.0
WALL, FLOOR = 2.0, 1.6
def funda(depth):
    outer = rrect(CW+2*WALL, CD+2*WALL, CR+WALL, depth+FLOOR)
    cav = rrect(CW, CD, CR, depth+1, FLOOR)
    hole = rrect(22, 12, 6, FLOOR+2, -1)   # hueco para empujar la botella
    return outer - cav - hole
def save(man, name):
    mesh = man.to_mesh()
    trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts).export(f"{out}/{name}")
    print(name, man.bounding_box())
save(funda(45.0), "funda_pocketbac_test.stl")
# anillo de prueba rápido: solo 10 mm, sin piso
ring = rrect(CW+2*WALL, CD+2*WALL, CR+WALL, 10) - rrect(CW, CD, CR, 12, -1)
save(ring, "anillo_prueba_ajuste.stl")
