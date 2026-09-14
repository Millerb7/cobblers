// EXP-017 Task A (vein-size check): a 256x256 flat world at y=100 with every Resources chance set to 0,
// so the underground is only WorldPainter's stone mix (stone/granite/diorite/andesite from y=0 up,
// deepslate/tuff below). Used as a clean host for in-game `/place feature` counts.
//   wpscript stone_block.js <world name>
var Material = Java.type("org.pepsoft.minecraft.Material");
var Resources = Java.type("org.pepsoft.worldpainter.layers.Resources");
var RES = Java.type("org.pepsoft.worldpainter.layers.exporters.ResourcesExporter$ResourcesExporterSettings");
var File = Java.type("java.io.File");
var Anchor = Java.type("org.pepsoft.worldpainter.Dimension$Anchor");

var name = arguments.length > 0 ? arguments[0] : "exp017-stone-block";
var hm = wp.getHeightMap().fromFile(scriptDir + "/heightmap100.png").go();
var platform = wp.getMapFormat().withId("org.pepsoft.anvil.1.20.5").go();
var world = wp.createWorld().fromHeightMap(hm).fromLevels(0, 255).toLevels(0, 255)
    .withWaterLevel(62).withMapFormat(platform).go();
world.setName(name);
var dim = world.getDimension(Anchor.NORMAL_DETAIL);
var settings = dim.getLayerSettings(Resources.INSTANCE);
if (settings == null) {
    settings = RES.defaultSettings(world.getPlatform(), dim.getAnchor(), dim.getMinHeight(), dim.getMaxHeight());
}
settings.getMaterials().forEach(function (m) { settings.setChance(m, 0); });
dim.setLayerSettings(Resources.INSTANCE, settings);
var out = new File(scriptDir, "exports");
out.mkdirs();
wp.exportWorld(world).toDirectory(out.getAbsolutePath()).go();
print("EXPORTED " + name + " resources chances set to 0 for " + settings.getMaterials().size() + " materials");
