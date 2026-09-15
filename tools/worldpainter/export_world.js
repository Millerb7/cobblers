// Import the canonical heightmap into a new WorldPainter world and export it for Minecraft 1.21.1.
//
// Run through tools/reexport.py, which supplies the seed in the environment
// (COBBLERS_WP_SEED) so it never appears in arguments or logs. Parameters:
//   --heightmap=<png>          16-bit greyscale heightmap (land_8k_16_eroded.png)
//   --name=<world name>        export folder name
//   --out=<dir>                directory the world folder is created in
//   --world-file=<path>        where to save the WorldPainter .world project
//   --image-low=<double>       image level mapped to --world-low
//   --image-high=<double>      image level mapped to --world-high
//   --world-low=<int> --world-high=<int> --water=<int>
//   --margin=<blocks>          ocean tiles added around the image on every side
//   --spawn-x=<int> --spawn-z=<int>
//   --border-centre=<int> --border-size=<int>
//   --paint=<manifest.json>    optional: paint biomes, terrain, vegetation and water (tools/worldpainter/paint.js)
//   --paint-script=<paint.js>  required with --paint
//
// The mapping is a straight line through (image-low, world-low) and
// (image-high, world-high). WorldPainter's world levels are whole numbers, so a
// fractional Y at image level 0 is expressed with a fractional image level
// instead: the line is identical.
var System = Java.type("java.lang.System");
var Long = Java.type("java.lang.Long");
var Point = Java.type("java.awt.Point");
var BufferedImage = Java.type("java.awt.image.BufferedImage");
var BitmapHeightMap = Java.type("org.pepsoft.worldpainter.heightMaps.BitmapHeightMap");
var TransformingHeightMap = Java.type("org.pepsoft.worldpainter.heightMaps.TransformingHeightMap");
var HeightMapImporter = Java.type("org.pepsoft.worldpainter.importing.HeightMapImporter");
var TileFactoryFactory = Java.type("org.pepsoft.worldpainter.TileFactoryFactory");
var Terrain = Java.type("org.pepsoft.worldpainter.Terrain");
var Configuration = Java.type("org.pepsoft.worldpainter.Configuration");
var Anchor = Java.type("org.pepsoft.worldpainter.Dimension$Anchor");

function param(key) {
    var v = params.get(key);
    if (v == null) {
        throw "missing --" + key;
    }
    return String(v);
}

var seedText = System.getenv("COBBLERS_WP_SEED");
if (seedText == null) {
    throw "COBBLERS_WP_SEED is not set; refusing to export with a random seed";
}
var seed = Long.parseLong(seedText);

var imageLow = parseFloat(param("image-low")), imageHigh = parseFloat(param("image-high"));
var worldLow = parseInt(param("world-low")), worldHigh = parseInt(param("world-high")), water = parseInt(param("water"));
var margin = parseInt(param("margin"));

var platform = wp.getMapFormat().withId("org.pepsoft.anvil.1.20.5").go();
print("map format: " + platform.displayName + " (" + platform.id + ")");

// Build limits: the platform default that holds the terrain and water, as ImportHeightMapOp does
var minHeight = null, maxHeight = null;
for each (var h in platform.minHeights) {
    if (minHeight === null && h <= platform.minZ && h <= Math.min(worldLow, water)) { minHeight = h; }
}
for each (var h2 in platform.maxHeights) {
    if (maxHeight === null && h2 >= platform.standardMaxHeight && h2 > Math.max(worldHigh, water)) { maxHeight = h2; }
}
print("build limits: " + minHeight + " .. " + maxHeight);

var heightMap = wp.getHeightMap().fromFile(param("heightmap")).go();
print("heightmap: " + heightMap.getName() + " " + heightMap.getWidth() + "x" + heightMap.getHeight()
    + ", bit depth " + heightMap.getBitDepth() + ", floating point " + heightMap.isFloatingPoint()
    + ", signed " + heightMap.isSigned() + ", alpha " + heightMap.hasAlpha()
    + ", value range " + heightMap.getRange()[0] + ".." + heightMap.getRange()[1]);
if (heightMap.getBitDepth() != 16) {
    throw "expected a 16-bit heightmap, got " + heightMap.getBitDepth();
}

// Fixed noise seed so repeated exports are identical
var tileFactory = TileFactoryFactory.createNoiseTileFactory(20260913, Terrain.GRASS, minHeight, maxHeight, 58, water, false, true, 20, 1.0);
var theme = Configuration.getInstance().getHeightMapDefaultTheme();
if (theme != null) {
    tileFactory.setTheme(theme);
}

function importer(hm, onlyRaise) {
    var imp = new HeightMapImporter();
    imp.setHeightMap(hm);
    imp.setImageFile(heightMap.getImageFile());
    imp.setImageLowLevel(imageLow);
    imp.setImageHighLevel(imageHigh);
    imp.setWorldLowLevel(worldLow);
    imp.setWorldHighLevel(worldHigh);
    imp.setWorldWaterLevel(water);
    imp.setMinHeight(minHeight);
    imp.setMaxHeight(maxHeight);
    imp.setTileFactory(tileFactory);
    imp.setPlatform(platform);
    imp.setMinecraftSeed(seed);
    imp.setName(param("name"));
    imp.setOnlyRaise(onlyRaise);
    return imp;
}

var t0 = System.currentTimeMillis();
var world = importer(heightMap, false).importToNewWorld(Anchor.NORMAL_DETAIL, null);
var dim = world.getDimension(Anchor.NORMAL_DETAIL);
print("imported landmass: " + dim.getTileCount() + " tiles in " + ((System.currentTimeMillis() - t0) / 1000) + " s");

// Ocean margin: a zero-valued image covering the canvas, only creating tiles where none exist.
// Existing tiles are untouched because onlyRaise never lowers and the margin level equals the lowest landmass level.
var side = heightMap.getWidth() + 2 * margin;
var blank = new BufferedImage(side, side, BufferedImage.TYPE_USHORT_GRAY);
var marginMap = new TransformingHeightMap("margin", BitmapHeightMap.build().withName("margin").withImage(blank).now(), 1.0, 1.0, -margin, -margin, 0.0);
t0 = System.currentTimeMillis();
importer(marginMap, true).importToDimension(dim, true, null);
print("with margin: " + dim.getTileCount() + " tiles in " + ((System.currentTimeMillis() - t0) / 1000) + " s; extent in tiles x "
    + dim.getLowestX() + ".." + dim.getHighestX() + ", z " + dim.getLowestY() + ".." + dim.getHighestY());

// Optional paint pass from 8-bit maps aligned with the heightmap (pixel = block), described by a manifest
if (params.get("paint") != null) {
    load(param("paint-script"));
    t0 = System.currentTimeMillis();
    paintWorld(world, dim, param("paint"));
    print("painted in " + ((System.currentTimeMillis() - t0) / 1000) + " s");
}

// Export settings: no WorldPainter border or wall, let Minecraft populate nothing, Minecraft world border as configured
dim.setPopulate(false);
dim.setBorder(null);
dim.setWallType(null);
dim.setRoofType(null);
world.setSpawnPoint(new Point(parseInt(param("spawn-x")), parseInt(param("spawn-z"))));
world.setMapFeatures(true);
var bs = world.getBorderSettings();
bs.setCentreX(parseInt(param("border-centre")));
bs.setCentreY(parseInt(param("border-centre")));
bs.setSize(parseInt(param("border-size")));
bs.setSizeLerpTarget(parseInt(param("border-size")));
bs.setSizeLerpTime(0);

print("generator: " + dim.getGenerator() + "; populate " + dim.isPopulate() + "; subsurface " + dim.getSubsurfaceMaterial()
    + "; bottomless " + dim.isBottomless() + "; top layer depth " + dim.getTopLayerMinDepth() + "+" + dim.getTopLayerVariation());
print("theme: " + (theme == null ? "WorldPainter default" : theme.getClass().getName()));
var layerSettings = dim.getAllLayerSettings();
for each (var layer in layerSettings.keySet()) {
    var s = layerSettings.get(layer);
    print("layer settings: " + layer.getName() + " -> " + s.getClass().getSimpleName() + (s.isApplyEverywhere ? " apply everywhere " + s.isApplyEverywhere() : ""));
}
print("minimum layers (applied everywhere): " + dim.getMinimumLayers());

t0 = System.currentTimeMillis();
wp.saveWorld(world).toFile(param("world-file")).go();
print("saved " + param("world-file") + " in " + ((System.currentTimeMillis() - t0) / 1000) + " s");

t0 = System.currentTimeMillis();
wp.exportWorld(world).toDirectory(param("out")).go();
print("exported " + param("name") + " to " + param("out") + " in " + ((System.currentTimeMillis() - t0) / 1000) + " s");
