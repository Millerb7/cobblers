// EXP-014 test 1: Resources layer with a modded ore.
// Part A: supported API. ResourcesExporterSettings only knows a fixed vanilla material map; try to
//         set a chance for cobblemon:thunder_stone_ore through the public setter.
// Part B: unsupported reflection injection into the private settings map, to see whether the
//         exporter itself would write a non-vanilla block. NOT a GUI/script-supported feature.
load(scriptDir + "/common.js");
var Resources = Java.type("org.pepsoft.worldpainter.layers.Resources");
var RES = Java.type("org.pepsoft.worldpainter.layers.exporters.ResourcesExporter$ResourcesExporterSettings");
var JClass = Java.type("java.lang.Class");
var Integer = Java.type("java.lang.Integer");
var Long = Java.type("java.lang.Long");

var mode = arguments.length > 0 ? arguments[0] : "api";
var world = makeWorld("exp014-resources-" + mode);
var dim = surface(world);
var settings = dim.getLayerSettings(Resources.INSTANCE);
if (settings == null) {
    settings = RES.defaultSettings(world.getPlatform(), dim.getAnchor(), dim.getMinHeight(), dim.getMaxHeight());
    print("no resources settings on dimension; using defaultSettings()");
}
var names = [];
settings.getMaterials().forEach(function (m) { names.push(m.toString()); });
print("Resources materials known to settings (" + names.length + "): " + names.join(", "));

var thunder = mat("cobblemon:thunder_stone_ore");
var deepThunder = mat("cobblemon:deepslate_thunder_stone_ore");
try {
    settings.setChance(thunder, 20);
    print("API setChance(cobblemon:thunder_stone_ore) succeeded");
} catch (e) {
    print("API setChance(cobblemon:thunder_stone_ore) FAILED: " + e);
}

if (mode === "reflect") {
    var f = RES.class.getDeclaredField("settings");
    f.setAccessible(true);
    var map = f.get(settings);
    var rsClass = JClass.forName("org.pepsoft.worldpainter.layers.exporters.ResourcesExporter$ResourceSettings");
    var ctor = rsClass.getDeclaredConstructor(Material.class, Integer.TYPE, Integer.TYPE, Integer.TYPE, Long.TYPE);
    ctor.setAccessible(true);
    map.put(thunder, ctor.newInstance(thunder, 0, 79, 20, 12345));
    map.put(deepThunder, ctor.newInstance(deepThunder, -64, -1, 20, 67890));
    print("reflection: injected thunder_stone_ore (0..79) and deepslate_thunder_stone_ore (-64..-1), chance 20");
}
dim.setLayerSettings(Resources.INSTANCE, settings);
exportTo(world);
