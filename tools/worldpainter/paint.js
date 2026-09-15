// Paint pass for export_world.js: loaded with load(), defines paintWorld(world, dim, manifestPath).
//
// The manifest (written by tools/paint_maps.py) lists 8-bit greyscale PNGs aligned with the heightmap,
// pixel (x, y) = block (x, z):
//   biomes   value = WorldPainter biome id, 255 = leave automatic
//   terrain  value = code; terrain_codes maps code -> Terrain name; 0 = leave the theme's terrain
//   trees    [{layer: "DeciduousForest"|"PineForest"|"SwampLand"|"Jungle", map}]   value 0-15 = density
//   plants   [{name, map, plants: {"<plant name>": occurrence}}]                     value 0/1
//   objects  [{layer, map, objects: [{file, frequency, offset: [x, z, y], extend_foundation, rotate, mirror}]}]
//            one custom object layer per entry; map value 15 marks a column that gets exactly one object,
//            chosen from the entry's objects by frequency (see the placement rule at paintObjects)
//   frost    map, value 0/1
//   water    [{name, level, x, z, mask}]  mask is a crop whose pixel (i, j) = block (x + i, z + j); 1 = raise water to level
//            [{name, x, z, levels}]       levels is a crop whose value is the water level y of that column; 0 = none
//            water is only ever raised, never lowered below what an earlier entry or the sea set
var ImageIO = Java.type("javax.imageio.ImageIO");
var JFile = Java.type("java.io.File");
var Files = Java.type("java.nio.file.Files");
var Paths = Java.type("java.nio.file.Paths");
var JString = Java.type("java.lang.String");
var BiomeLayer = Java.type("org.pepsoft.worldpainter.layers.Biome");
var FrostLayer = Java.type("org.pepsoft.worldpainter.layers.Frost");
var PlantLayer = Java.type("org.pepsoft.worldpainter.layers.plants.PlantLayer");
var PlantSettings = Java.type("org.pepsoft.worldpainter.layers.plants.PlantLayer$PlantSettings");
var Plants = Java.type("org.pepsoft.worldpainter.layers.plants.Plants");
var TerrainT = Java.type("org.pepsoft.worldpainter.Terrain");
var ColorT = Java.type("java.awt.Color");
var TREE_LAYERS = {
    DeciduousForest: Java.type("org.pepsoft.worldpainter.layers.DeciduousForest").INSTANCE,
    PineForest: Java.type("org.pepsoft.worldpainter.layers.PineForest").INSTANCE,
    SwampLand: Java.type("org.pepsoft.worldpainter.layers.SwampLand").INSTANCE,
    Jungle: Java.type("org.pepsoft.worldpainter.layers.Jungle").INSTANCE
};

function terrainIndex(name) {
    var values = TerrainT.VALUES;
    for (var i = 0; i < values.length; i++) {
        if (values[i] != null && values[i].name() == name) {
            return i;
        }
    }
    throw "unknown terrain " + name;
}

function mapFile(base, rel) {
    return new JFile(base, rel).getAbsolutePath();
}

function plantByName(name) {
    var all = Plants.ALL_PLANTS;
    for (var i = 0; i < all.length; i++) {
        if (all[i].getName() == name) {
            return i;
        }
    }
    throw "unknown plant " + name;
}

var CustomObjectManager = Java.type("org.pepsoft.worldpainter.plugins.CustomObjectManager");
var Bo2Layer = Java.type("org.pepsoft.worldpainter.layers.Bo2Layer");
var Bo2ObjectTube = Java.type("org.pepsoft.worldpainter.layers.bo2.Bo2ObjectTube");
var WPObject = Java.type("org.pepsoft.worldpainter.objects.WPObject");
var Point3i = Java.type("javax.vecmath.Point3i");
var ArrayList = Java.type("java.util.ArrayList");
var JInteger = Java.type("java.lang.Integer");
var JBoolean = Java.type("java.lang.Boolean");

// Custom object layers. WorldPainter 2.27.1 Bo2LayerExporter, read from its bytecode: at every column where
// x % gridX == 0 and z % gridY == 0 and the layer value v > 0, it places one object when
// Random.nextInt(density * 64) <= v * v. With grid 1 and density 1 that is always true for v >= 8, so the
// map marks exact positions and tools/paint_maps.py decides spacing. Which object is placed is WorldPainter's
// weighted pick by frequency. Above the terrain an object only fills air and plants, never ground or another
// object's blocks.
function paintObjects(world, base, entry) {
    var list = new ArrayList();
    entry.objects.forEach(function (o) {
        var obj = CustomObjectManager.getInstance().loadObject(new JFile(o.file));
        obj.setAttribute(WPObject.ATTRIBUTE_OFFSET, new Point3i(o.offset[0], o.offset[1], o.offset[2]));
        obj.setAttribute(WPObject.ATTRIBUTE_FREQUENCY, JInteger.valueOf(o.frequency));
        obj.setAttribute(WPObject.ATTRIBUTE_RANDOM_ROTATION, JBoolean.valueOf(o.rotate !== false));
        obj.setAttribute(WPObject.ATTRIBUTE_RANDOM_MIRRORING_ONLY, JBoolean.FALSE);
        obj.setAttribute(WPObject.ATTRIBUTE_SPAWN_ON_LAND, JBoolean.TRUE);
        obj.setAttribute(WPObject.ATTRIBUTE_SPAWN_IN_WATER, JBoolean.valueOf(o.in_water === true));
        obj.setAttribute(WPObject.ATTRIBUTE_SPAWN_ON_WATER, JBoolean.FALSE);
        obj.setAttribute(WPObject.ATTRIBUTE_COLLISION_MODE, JInteger.valueOf(WPObject.COLLISION_MODE_NONE));
        obj.setAttribute(WPObject.ATTRIBUTE_LEAF_DECAY_MODE, JInteger.valueOf(WPObject.LEAF_DECAY_OFF));
        obj.setAttribute(WPObject.ATTRIBUTE_HEIGHT_MODE, JInteger.valueOf(WPObject.HEIGHT_MODE_TERRAIN));
        obj.setAttribute(WPObject.ATTRIBUTE_VERTICAL_OFFSET, JInteger.valueOf(o.vertical_offset || 0));
        obj.setAttribute(WPObject.ATTRIBUTE_Y_VARIATION, JInteger.valueOf(0));
        obj.setAttribute(WPObject.ATTRIBUTE_EXTEND_FOUNDATION, JBoolean.valueOf(o.extend_foundation === true));
        list.add(obj);
    });
    var layer = new Bo2Layer(new Bo2ObjectTube(entry.layer, list), "cobblers_" + entry.layer, null);
    layer.setDensity(1);
    layer.setGridX(1);
    layer.setGridY(1);
    layer.setRandomDisplacement(0);
    var hm = wp.getHeightMap().fromFile(mapFile(base, entry.map)).go();
    wp.applyHeightMap(hm).toWorld(world).applyToLayer(layer).fromLevel(15).toLevel(15).go();
    return list.size();
}

function setField(obj, name, value) {
    var f = PlantSettings.class.getDeclaredField(name);
    f.setAccessible(true);
    f.set(obj, value);
}

function paintWorld(world, dim, manifestPath) {
    var manifestFile = new JFile(manifestPath);
    var base = manifestFile.getParentFile();
    var m = JSON.parse(new JString(Files.readAllBytes(Paths.get(manifestPath)), "UTF-8"));
    var t;

    if (m.biomes) {
        t = java.lang.System.currentTimeMillis();
        var hm = wp.getHeightMap().fromFile(mapFile(base, m.biomes)).go();
        var op = wp.applyHeightMap(hm).toWorld(world).applyToLayer(BiomeLayer.INSTANCE);
        for (var v = 0; v < 255; v++) {
            op = op.fromLevel(v).toLevel(v);
        }
        op.go();
        print("paint: biomes (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    }

    if (m.terrain) {
        t = java.lang.System.currentTimeMillis();
        var thm = wp.getHeightMap().fromFile(mapFile(base, m.terrain)).go();
        var top = wp.applyHeightMap(thm).toWorld(world).applyToTerrain();
        for (var code in m.terrain_codes) {
            top = top.fromLevel(parseInt(code)).toTerrain(terrainIndex(m.terrain_codes[code]));
        }
        top.go();
        print("paint: terrain " + JSON.stringify(m.terrain_codes) + " (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    }

    (m.trees || []).forEach(function (tr) {
        t = java.lang.System.currentTimeMillis();
        var layer = TREE_LAYERS[tr.layer];
        if (layer == null) {
            throw "unknown tree layer " + tr.layer;
        }
        var hm2 = wp.getHeightMap().fromFile(mapFile(base, tr.map)).go();
        var op2 = wp.applyHeightMap(hm2).toWorld(world).applyToLayer(layer);
        for (var d = 1; d <= 15; d++) {
            op2 = op2.fromLevel(d).toLevel(d);
        }
        op2.go();
        print("paint: trees " + tr.layer + " (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    });

    (m.objects || []).forEach(function (entry) {
        t = java.lang.System.currentTimeMillis();
        var n = paintObjects(world, base, entry);
        print("paint: objects " + entry.layer + ", " + n + " variants (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    });

    (m.plants || []).forEach(function (pl) {
        t = java.lang.System.currentTimeMillis();
        var layer = new PlantLayer(pl.name, "Cobblers paint: " + pl.name, ColorT.GREEN);
        for (var name in pl.plants) {
            var s = new PlantSettings();
            setField(s, "occurrence", java.lang.Short.valueOf(pl.plants[name]));
            setField(s, "growthFrom", java.lang.Integer.valueOf(0));
            setField(s, "growthTo", java.lang.Integer.valueOf(0));
            layer.setSettings(plantByName(name), s);
        }
        var hm3 = wp.getHeightMap().fromFile(mapFile(base, pl.map)).go();
        wp.applyHeightMap(hm3).toWorld(world).applyToLayer(layer).fromLevel(1).toLevel(1).go();
        print("paint: plants " + pl.name + " (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    });

    if (m.frost) {
        t = java.lang.System.currentTimeMillis();
        var fhm = wp.getHeightMap().fromFile(mapFile(base, m.frost)).go();
        wp.applyHeightMap(fhm).toWorld(world).applyToLayer(FrostLayer.INSTANCE).fromLevel(1).toLevel(1).go();
        print("paint: frost (" + ((java.lang.System.currentTimeMillis() - t) / 1000) + " s)");
    }

    (m.water || []).forEach(function (w) {
        var img = ImageIO.read(new JFile(base, w.levels ? w.levels : w.mask));
        var raster = img.getRaster();
        var n = 0;
        for (var j = 0; j < img.getHeight(); j++) {
            for (var i = 0; i < img.getWidth(); i++) {
                var v = raster.getSample(i, j, 0);
                if (v <= 0) {
                    continue;
                }
                var level = w.levels ? v : w.level;
                // only ever raise: a river never lowers a lake it touches, or the sea
                if (level > dim.getWaterLevelAt(w.x + i, w.z + j)) {
                    dim.setWaterLevelAt(w.x + i, w.z + j, level);
                    n++;
                }
            }
        }
        print("paint: water " + w.name + (w.levels ? " (per-column levels)" : " level " + w.level) + " on " + n + " columns");
    });
}
