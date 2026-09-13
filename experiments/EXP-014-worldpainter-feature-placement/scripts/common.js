// EXP-014 shared helpers for wpscript (Nashorn). Loaded with load(scriptDir + "/common.js").
var Material = Java.type("org.pepsoft.minecraft.Material");
var Anchor = Java.type("org.pepsoft.worldpainter.Dimension$Anchor");
var File = Java.type("java.io.File");

// Material.get(String, Object...) — explicit overload so Nashorn does not guess.
function mat(name) {
    return Material["get(java.lang.String,java.lang.Object[])"](name, Java.to([], "java.lang.Object[]"));
}

// 256x256 flat world at y=80, water level 62, Minecraft 1.20.5 - 1.21.x map format.
function makeWorld(name) {
    var hm = wp.getHeightMap().fromFile(scriptDir + "/heightmap.png").go();
    var platform = wp.getMapFormat().withId("org.pepsoft.anvil.1.20.5").go();
    print("platform: " + platform.displayName + " (" + platform.id + ")");
    var world = wp.createWorld().fromHeightMap(hm).fromLevels(0, 255).toLevels(0, 255)
        .withWaterLevel(62).withMapFormat(platform).go();
    world.setName(name);
    return world;
}

function surface(world) {
    return world.getDimension(Anchor.NORMAL_DETAIL);
}

function exportTo(world) {
    var out = new File(scriptDir, "exports");
    out.mkdirs();
    wp.exportWorld(world).toDirectory(out.getAbsolutePath()).go();
    print("exported " + world.getName() + " to " + out.getAbsolutePath());
}
