// EXP-017 Task A: Underground Pockets calibration worlds, driven by wpscript (Nashorn).
//   wpscript pockets_sweep.js <spec> [<spec> ...]
// spec = name:block:frequency:scale:minLevel:maxLevel[:value[:dilute]]
//   block    full block ID, e.g. cobblemon:fire_stone_ore
//   value    layer value 1..15 applied everywhere (default 8 = what applyLayer uses for a nibble layer)
//   dilute   optional "host@count/oreCount" e.g. minecraft:stone@9/1 -> MixedMaterial NOISE mode with
//            rows (block, oreCount) and (host, count); only for the dilution variant
// Every world: 256x256 flat at y=100 from heightmap100.png (next to this script), map format
// org.pepsoft.anvil.1.20.5, exported to <scriptDir>/exports/<name>.
var Material = Java.type("org.pepsoft.minecraft.Material");
var MixedMaterial = Java.type("org.pepsoft.worldpainter.MixedMaterial");
var Row = Java.type("org.pepsoft.worldpainter.MixedMaterial$Row");
var Pockets = Java.type("org.pepsoft.worldpainter.layers.pockets.UndergroundPocketsLayer");
var Color = Java.type("java.awt.Color");
var File = Java.type("java.io.File");
var Anchor = Java.type("org.pepsoft.worldpainter.Dimension$Anchor");

function mat(name) {
    return Material["get(java.lang.String,java.lang.Object[])"](name, Java.to([], "java.lang.Object[]"));
}

var hm = wp.getHeightMap().fromFile(scriptDir + "/heightmap100.png").go();
var platform = wp.getMapFormat().withId("org.pepsoft.anvil.1.20.5").go();
var out = new File(scriptDir, "exports");
out.mkdirs();

for (var i = 0; i < arguments.length; i++) {
    var p = String(arguments[i]).split(":");
    // block IDs contain a colon: name:ns:path:freq:scale:min:max[:value[:dilute]]
    var name = p[0], block = p[1] + ":" + p[2];
    var freq = parseInt(p[3]), scale = parseInt(p[4]), minLevel = parseInt(p[5]), maxLevel = parseInt(p[6]);
    var value = p.length > 7 && p[7] !== "" ? parseInt(p[7]) : 8;
    var mm;
    if (p.length > 8) {
        // dilute = host namespace:path@hostCount/oreCount, the host ID's colon was split too
        var rest = p.slice(8).join(":");
        var hostAt = rest.split("@"), counts = hostAt[1].split("/");
        var rows = Java.to([new Row(mat(block), parseInt(counts[1]), 1.0), new Row(mat(hostAt[0]), parseInt(counts[0]), 1.0)],
            "org.pepsoft.worldpainter.MixedMaterial$Row[]");
        mm = new MixedMaterial(name, rows, -1, null);
    } else {
        mm = MixedMaterial["create(java.lang.String,org.pepsoft.minecraft.Material)"](name, mat(block));
    }
    var world = wp.createWorld().fromHeightMap(hm).fromLevels(0, 255).toLevels(0, 255)
        .withWaterLevel(62).withMapFormat(platform).go();
    world.setName(name);
    var layer = new Pockets(name, mm, null, freq, minLevel, maxLevel, scale, Color.RED);
    wp.applyLayer(layer).toWorld(world).toLevel(value).go();
    var dim = world.getDimension(Anchor.NORMAL_DETAIL);
    var t0 = java.lang.System.currentTimeMillis();
    wp.exportWorld(world).toDirectory(out.getAbsolutePath()).go();
    print("EXPORTED " + name + " block=" + block + " freq=" + freq + " scale=" + scale + " levels=" + minLevel + ".." + maxLevel
        + " value=" + value + " layerValue(5,5)=" + dim.getLayerValueAt(layer, 5, 5) + " seed=" + dim.getSeed()
        + " height(5,5)=" + dim.getIntHeightAt(5, 5) + " topLayerDepth=" + dim.getTopLayerDepth(5, 5, dim.getIntHeightAt(5, 5))
        + " subsurface=" + dim.getSubsurfaceMaterial() + " mode=" + mm.getMode() + " ms=" + (java.lang.System.currentTimeMillis() - t0));
}
