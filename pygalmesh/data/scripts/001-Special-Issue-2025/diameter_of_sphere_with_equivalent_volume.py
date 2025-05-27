import math

# Konstanten
voxel_size = 0.015  # Kantenlänge eines Voxels mm
voxel_volume = voxel_size ** 3  # Volumen eines Voxels in mm³

# Anzahl der Voxel direkt im Skript definieren
num_voxels = 3.45e4 # <- Hier kannst du den Wert ändern

# Gesamtvolumen berechnen
V_voxel = num_voxels * voxel_volume

# Durchmesser der Kugel mit gleichem Volumen berechnen
# V = (4/3) * π * r³  -> r = ((3V) / (4π))^(1/3)
radius = ((3 * V_voxel) / (4 * math.pi)) ** (1/3)
diameter = 2 * radius

# Ausgabe
print(f"Anzahl der Voxel: {num_voxels}")
print(f"Gesamtvolumen: {V_voxel:.6f} mm³")
print(f"Durchmesser einer Kugel mit gleichem Volumen: {diameter:.6f} mm")
