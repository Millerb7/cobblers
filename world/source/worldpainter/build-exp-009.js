// Run from the repository root: wpscript world/source/worldpainter/build-exp-009.js <scale-percent> [export]
// API used here is documented at https://www.worldpainter.net/trac/wiki/Scripting/API
var root = 'world/source/exp-009/';
if (arguments.length < 1) throw 'Pass scale percent derived from region.json blocks_per_pixel (currently 100).';
var scale = parseInt(arguments[0], 10);
if (!(scale > 0)) throw 'Scale percent must be a positive integer.';
var mapFormat = wp.getMapFormat().withId('org.pepsoft.anvil.1.20.5').go();
var heightMap = wp.getHeightMap().fromFile(root + 'masks/heightmap.png').go();
var categoryMap = wp.getHeightMap().fromFile(root + 'masks/terrain-categories.png').go();
var forestMask = wp.getHeightMap().fromFile(root + 'masks/forest.png').go();
var transitionMap = wp.getHeightMap().fromFile(root + 'masks/transition-bands.png').go();
var roadMask = wp.getHeightMap().fromFile(root + 'masks/roads-trails.png').go();
var eventMask = wp.getHeightMap().fromFile(root + 'masks/event-reservations.png').go();

var world = wp.createWorld()
    .fromHeightMap(heightMap).scale(scale)
    .fromLevels(0, 255).toLevels(0, 255)
    .withWaterLevel(62).withMapFormat(mapFormat)
    .withLowerBuildLimit(-64).withUpperBuildLimit(320).go();

// Exact category values: 1 plains, 2 forest edge, 3 forest core,
// 4 mountain/rock, 5 bank, 6 river. Values are never antialiased.
wp.applyHeightMap(categoryMap).toWorld(world).scale(scale).applyToTerrain()
    .fromLevels(1, 3).toTerrain(0)  // grass
    .fromLevel(4).toTerrain(29)    // rock
    .fromLevel(5).toTerrain(2)     // sand
    .fromLevel(6).toTerrain(36)    // beach/ocean floor below water
    .go();

var biomes = wp.getLayer().withName('Biomes').go();
wp.applyHeightMap(categoryMap).toWorld(world).scale(scale).applyToLayer(biomes)
    .fromLevel(1).toLevel(1)   // plains
    .fromLevel(2).toLevel(1)   // meadow/forest edge
    .fromLevel(3).toLevel(4)   // forest core
    .fromLevel(4).toLevel(3)   // windswept hills
    .fromLevel(5).toLevel(16)  // beach
    .fromLevel(6).toLevel(7)   // river
    .go();

var deciduous = wp.getLayer().withName('Deciduous').go();
wp.applyHeightMap(forestMask).toWorld(world).scale(scale).applyToLayer(deciduous)
    .fromLevel(0).toLevel(0).fromLevel(255).toLevel(12).go();
wp.applyHeightMap(transitionMap).toWorld(world).scale(scale).applyToLayer(deciduous)
    .fromLevel(85).toLevel(4).go();

// Planning overlays remain visible in the editable .world but do not become
// gameplay blocks. Post-export commands build the road, lots and structures.
var annotations = wp.getLayer().withName('Annotations').go();
wp.applyHeightMap(roadMask).toWorld(world).scale(scale).applyToLayer(annotations)
    .fromLevel(255).toLevel(6).go();
wp.applyHeightMap(eventMask).toWorld(world).scale(scale).applyToLayer(annotations)
    .fromLevel(128).toLevel(2).fromLevel(255).toLevel(4).go();

wp.saveWorld(world).toFile('experiments/EXP-009-automated-hex-world/runtime/cobblers-exp-009.world').go();
if (arguments.length > 1 && arguments[1] == 'export') {
    wp.exportWorld(world).toDirectory('experiments/EXP-009-automated-hex-world/runtime/export').go();
}
