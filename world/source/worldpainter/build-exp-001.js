// Run from the repository root:
// wpscript world/source/worldpainter/build-exp-001.js 100 [export]
var root = 'world/source/exp-001/';
if (arguments.length < 1) throw 'Pass scale percent (100 for one block per pixel).';
var scale = parseInt(arguments[0], 10);
if (!(scale > 0)) throw 'Scale percent must be a positive integer.';

var mapFormat = wp.getMapFormat().withId('org.pepsoft.anvil.1.20.5').go();
var heightMap = wp.getHeightMap().fromFile(root + 'masks/heightmap.png').go();
var categoryMap = wp.getHeightMap().fromFile(root + 'masks/terrain-categories.png').go();
var forestMask = wp.getHeightMap().fromFile(root + 'masks/forest.png').go();

var world = wp.createWorld()
    .fromHeightMap(heightMap).scale(scale)
    .fromLevels(0, 255).toLevels(0, 255)
    .withWaterLevel(62).withMapFormat(mapFormat)
    .withLowerBuildLimit(-64).withUpperBuildLimit(320).go();

// 1 grass, 2 forest floor, 3 rocky upland, 4 beach, 5 ocean floor.
wp.applyHeightMap(categoryMap).toWorld(world).scale(scale).applyToTerrain()
    .fromLevel(1).toTerrain(0)
    .fromLevel(2).toTerrain(0)
    .fromLevel(3).toTerrain(29)
    .fromLevel(4).toTerrain(2)
    .fromLevel(5).toTerrain(36)
    .go();

var biomes = wp.getLayer().withName('Biomes').go();
wp.applyHeightMap(categoryMap).toWorld(world).scale(scale).applyToLayer(biomes)
    .fromLevel(1).toLevel(1)
    .fromLevel(2).toLevel(4)
    .fromLevel(3).toLevel(3)
    .fromLevel(4).toLevel(16)
    .fromLevel(5).toLevel(0)
    .go();

var deciduous = wp.getLayer().withName('Deciduous').go();
wp.applyHeightMap(forestMask).toWorld(world).scale(scale).applyToLayer(deciduous)
    .fromLevel(0).toLevel(0).fromLevel(255).toLevel(10).go();

var annotations = wp.getLayer().withName('Annotations').go();
var routeMask = wp.getHeightMap().fromFile(root + 'masks/routes.png').go();
var eventMask = wp.getHeightMap().fromFile(root + 'masks/events.png').go();
wp.applyHeightMap(routeMask).toWorld(world).scale(scale).applyToLayer(annotations)
    .fromLevel(255).toLevel(6).go();
wp.applyHeightMap(eventMask).toWorld(world).scale(scale).applyToLayer(annotations)
    .fromLevel(255).toLevel(4).go();

wp.saveWorld(world).toFile('experiments/EXP-001-curated-route/runtime/exp001-f4-pallet.world').go();
if (arguments.length > 1 && arguments[1] == 'export') {
    wp.exportWorld(world).toDirectory('experiments/EXP-001-curated-route/runtime/export').go();
}
