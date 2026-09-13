// EXP-014 test 3: Custom Objects (Bo2Layer) with .schem (Sponge v2 + v3) and structure .nbt objects
// containing Cobblemon blocks and cobblemon:berry block entities, restricted to one biome by a filter.
// argv: <object file names in objects/ ...>; params: --level=<1..15> --density=<n> --world=<name>
load(scriptDir + "/common.js");
var Bo2ObjectTube = Java.type("org.pepsoft.worldpainter.layers.bo2.Bo2ObjectTube");
var Bo2Layer = Java.type("org.pepsoft.worldpainter.layers.Bo2Layer");
var ArrayList = Java.type("java.util.ArrayList");
var Color = Java.type("java.awt.Color");

var level = params.containsKey("level") ? parseInt(params.get("level")) : 2;
var density = params.containsKey("density") ? parseInt(params.get("density")) : 20;
var world = makeWorld(params.containsKey("world") ? params.get("world") : "exp014-objects");

// Paint biomes: west half (mask 255) forest, east half (mask 0) plains.
var forest = wp.getBiomeId().withName("forest").go();
var plains = wp.getBiomeId().withName("plains").go();
print("biome ids: forest=" + forest + " plains=" + plains);
var mask = wp.getHeightMap().fromFile(scriptDir + "/biomemask.png").go();
var biomes = wp.getLayer().withName("Biomes").go();
wp.applyHeightMap(mask).toWorld(world).applyToLayer(biomes).fromLevel(255).toLevel(forest).fromLevel(0).toLevel(plains).go();

var files = new ArrayList();
for (var i = 0; i < arguments.length; i++) {
    files.add(new File(scriptDir + "/objects/" + arguments[i]));
}
var tube = Bo2ObjectTube.load("cobblemon_objects", files);
tube.getAllObjects().forEach(function (o) {
    var te = o.getTileEntities();
    print("loaded object " + o.getName() + " dims=" + o.getDimensions() + " offset=" + o.getOffset()
        + " tileEntities=" + (te == null ? 0 : te.size())
        + (te == null ? "" : " firstTE=" + te.get(0).toNBT()));
});
var layer = new Bo2Layer(tube, "Cobblemon objects", Color.ORANGE);
layer.setDensity(density);

var onlyForest = wp.createFilter().onlyOnBiome(forest).go();
wp.applyLayer(layer).toWorld(world).toLevel(level).withFilter(onlyForest).go();
var dim = surface(world);
print("layer value at (10,10) forest=" + dim.getLayerValueAt(layer, 10, 10) + ", at (200,10) plains=" + dim.getLayerValueAt(layer, 200, 10)
    + "; biome at (10,10)=" + dim.getLayerValueAt(biomes, 10, 10) + " at (200,10)=" + dim.getLayerValueAt(biomes, 200, 10));
exportTo(world);
