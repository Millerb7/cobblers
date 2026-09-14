// EXP-017 Task A verification: worlds with one or more Underground Pockets layers, from a JSON plan.
//   wpscript pockets_verify.js <plan.json>
// plan.json: [{"world": name, "layers": [{"name", "block", "host"?, "ore": oreCount?, "hostCount"?,
//              "frequency", "scale", "min", "max", "value"?}]}]
// A layer with "host" uses MixedMaterial NOISE mode, rows (block x ore) + (host x hostCount): each
// pocket cell becomes the ore with probability ore/(ore+hostCount), else the host block.
// Same world setup as pockets_sweep.js: 256x256 flat at y=100 (heightmap100.png), anvil 1.20.5.
var Files = Java.type("java.nio.file.Files");
var Paths = Java.type("java.nio.file.Paths");
var JString = Java.type("java.lang.String");
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

var plan = JSON.parse(new JString(Files.readAllBytes(Paths.get(arguments[0])), "UTF-8"));
var hm = wp.getHeightMap().fromFile(scriptDir + "/heightmap100.png").go();
var platform = wp.getMapFormat().withId("org.pepsoft.anvil.1.20.5").go();
var out = new File(scriptDir, "exports");
out.mkdirs();

plan.forEach(function (w) {
    var world = wp.createWorld().fromHeightMap(hm).fromLevels(0, 255).toLevels(0, 255)
        .withWaterLevel(62).withMapFormat(platform).go();
    world.setName(w.world);
    w.layers.forEach(function (l) {
        var mm;
        if (l.host) {
            var rows = Java.to([new Row(mat(l.block), l.ore, 1.0), new Row(mat(l.host), l.hostCount, 1.0)],
                "org.pepsoft.worldpainter.MixedMaterial$Row[]");
            mm = new MixedMaterial(l.name, rows, -1, null);
        } else {
            mm = MixedMaterial["create(java.lang.String,org.pepsoft.minecraft.Material)"](l.name, mat(l.block));
        }
        var layer = new Pockets(l.name, mm, null, l.frequency, l.min, l.max, l.scale, Color.RED);
        wp.applyLayer(layer).toWorld(world).toLevel(l.value ? l.value : 8).go();
        print("layer " + l.name + " " + l.block + (l.host ? " NOISE " + l.ore + ":" + l.hostCount + " " + l.host : "")
            + " f=" + l.frequency + " s=" + l.scale + " y=" + l.min + ".." + l.max + " value=" + (l.value ? l.value : 8)
            + " mode=" + mm.getMode());
    });
    wp.exportWorld(world).toDirectory(out.getAbsolutePath()).go();
    print("EXPORTED " + w.world + " seed=" + world.getDimension(Anchor.NORMAL_DETAIL).getSeed());
});
