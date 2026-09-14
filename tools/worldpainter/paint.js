// Paint pass for export_world.js: loaded with load(), defines paintWorld(world, dim, manifestPath).
//
// The manifest (written by tools/paint_maps.py) lists 8-bit greyscale PNGs aligned with the heightmap,
// pixel (x, y) = block (x, z):
//   biomes   value = WorldPainter biome id, 255 = leave automatic
//   terrain  value = code; terrain_codes maps code -> Terrain name; 0 = leave the theme's terrain
//   trees    [{layer: "DeciduousForest"|"PineForest"|"SwampLand"|"Jungle", map}]   value 0-15 = density
//   plants   [{name, map, plants: {"<plant name>": occurrence}}]                     value 0/1
//   frost    map, value 0/1
//   water    [{name, level, x, z, mask}]  mask is a crop whose pixel (i, j) = block (x + i, z + j); 1 = raise water to level
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
        var img = ImageIO.read(new JFile(base, w.mask));
        var raster = img.getRaster();
        var n = 0;
        for (var j = 0; j < img.getHeight(); j++) {
            for (var i = 0; i < img.getWidth(); i++) {
                if (raster.getSample(i, j, 0) > 0) {
                    dim.setWaterLevelAt(w.x + i, w.z + j, w.level);
                    n++;
                }
            }
        }
        print("paint: water " + w.name + " level " + w.level + " on " + n + " columns");
    });
}
