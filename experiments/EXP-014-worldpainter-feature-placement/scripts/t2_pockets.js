// EXP-014 test 2: Underground Pockets custom layers whose material is a modded ore block ID.
load(scriptDir + "/common.js");
var MixedMaterial = Java.type("org.pepsoft.worldpainter.MixedMaterial");
var Pockets = Java.type("org.pepsoft.worldpainter.layers.pockets.UndergroundPocketsLayer");
var Color = Java.type("java.awt.Color");

var world = makeWorld("exp014-pockets");
// (name, MixedMaterial, Terrain, frequency 1..1000, minLevel, maxLevel, scale, paint)
var fire = new Pockets("fire_stone_ore", MixedMaterial["create(java.lang.String,org.pepsoft.minecraft.Material)"]("fire_stone_ore", mat("cobblemon:fire_stone_ore")),
    null, 50, 0, 70, 50, Color.RED);
var deepFire = new Pockets("deepslate_fire_stone_ore", MixedMaterial["create(java.lang.String,org.pepsoft.minecraft.Material)"]("deepslate_fire_stone_ore", mat("cobblemon:deepslate_fire_stone_ore")),
    null, 50, -64, -1, 50, Color.ORANGE);
wp.applyLayer(fire).toWorld(world).go();
wp.applyLayer(deepFire).toWorld(world).go();
print("applied pockets layers: " + fire.getName() + " (0..70), " + deepFire.getName() + " (-64..-1)");
exportTo(world);
