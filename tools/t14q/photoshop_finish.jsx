// C-T14Q Photoshop finishing (ExtendScript).  Placeholders __WORK__ / __VARIANT__ are replaced by the runner.
// Layer stack (bottom -> top): locked Blender base, ChatGPT raw (Preserve Details upscale), tower geometry restore,
// CC0 micro-texture (asphalt / paving), depth haze, grade, vignette, visible stamp (curves, unsharp, edge softness), grain.
#target photoshop
app.displayDialogs = DialogModes.NO;
app.preferences.rulerUnits = Units.PIXELS;

var WORK = "__WORK__";
var VARIANT = "__VARIANT__";
var LOG = [];
function log(s) { LOG.push(s); }
function F(n) { return new File(WORK + n); }
var doc = null;

function pasteFrom(name, label, mode, opacity, upscale) {
    var d = app.open(F(name));
    if (upscale) {
        try { d.resizeImage(UnitValue(4800, "px"), UnitValue(2700, "px"), 72, ResampleMethod.PRESERVEDETAILS2); log("resample: PRESERVEDETAILS2"); }
        catch (e1) { d.resizeImage(UnitValue(4800, "px"), UnitValue(2700, "px"), 72, ResampleMethod.PRESERVEDETAILS); log("resample: PRESERVEDETAILS (fallback)"); }
    }
    d.selection.selectAll(); d.selection.copy(); d.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    var L = doc.paste();
    L.name = label; L.blendMode = mode; L.opacity = opacity;
    log("layer: " + label);
    return L;
}

function maskChannel(name, chName) {
    var d = app.open(F(name));
    d.selection.selectAll(); d.selection.copy(); d.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    var ch = doc.channels.add();
    ch.name = chName; ch.kind = ChannelType.MASKEDAREA;
    doc.activeChannels = [ch];
    doc.paste();
    doc.selection.deselect();
    doc.activeChannels = doc.componentChannels;
    return ch;
}

function addMask(layer, ch) {
    doc.activeLayer = layer;
    doc.selection.load(ch, SelectionType.REPLACE);
    var d = new ActionDescriptor();
    d.putClass(charIDToTypeID("Nw  "), charIDToTypeID("Chnl"));
    var r2 = new ActionReference();
    r2.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Msk "));
    d.putReference(charIDToTypeID("At  "), r2);
    d.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("UsrM"), charIDToTypeID("RvlS"));
    executeAction(charIDToTypeID("Mk  "), d, DialogModes.NO);
    doc.selection.deselect();
    log("mask applied: " + layer.name);
}

function fillLayer(label, rgb, mode, opacity) {
    var L = doc.artLayers.add();
    L.name = label; L.blendMode = mode; L.opacity = opacity;
    doc.activeLayer = L;
    var c = new SolidColor();
    c.rgb.red = rgb[0]; c.rgb.green = rgb[1]; c.rgb.blue = rgb[2];
    doc.selection.selectAll();
    doc.selection.fill(c, ColorBlendMode.NORMAL, 100, false);
    doc.selection.deselect();
    log("fill layer: " + label);
    return L;
}

function stampVisible(label) {
    var t = doc.duplicate();
    t.flatten();
    t.selection.selectAll(); t.selection.copy();
    t.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    var L = doc.paste();
    L.name = label;
    log("stamp: " + label);
    return L;
}

try {
    doc = app.open(F("blender_base.png"));
    if (doc.mode != DocumentMode.RGB) doc.changeMode(ChangeMode.RGB);
    if (doc.bitsPerChannel != BitsPerChannelType.EIGHT) doc.bitsPerChannel = BitsPerChannelType.EIGHT;
    doc.resizeImage(undefined, undefined, 300, ResampleMethod.NONE);
    var base = doc.activeLayer;
    base.isBackgroundLayer = false;
    base.name = "00_BLENDER_BASE_LOCKED (verified mesh render)";
    log("doc " + doc.width + "x" + doc.height + " px @" + doc.resolution + " dpi");

    var chT = maskChannel("mask_tower.png", "mask_tower");
    var chF = maskChannel("mask_facade.png", "mask_facade");
    var chR = maskChannel("mask_road.png", "mask_road");
    var chW = maskChannel("mask_walk.png", "mask_walk");
    var chD = maskChannel("mask_depth.png", "mask_depth");
    var chV = maskChannel("mask_vignette.png", "mask_vignette");

    pasteFrom("gpt_raw.png", "01_CHATGPT_RAW_UPSCALED (Preserve Details)", BlendMode.NORMAL, 100, true);
    var L2 = pasteFrom("relit_tower.png", "02_TOWER_GEOMETRY_RESTORE (Blender detail + ChatGPT tone)", BlendMode.NORMAL, (VARIANT == "daylight") ? 78 : 52, false);
    addMask(L2, chF);

    var L3 = pasteFrom("tex_asphalt.png", "03_MICROTEXTURE_asphalt (Poly Haven CC0 asphalt_02)", BlendMode.SOFTLIGHT, 38, false);
    addMask(L3, chR);
    var L4 = pasteFrom("tex_paving.png", "04_MICROTEXTURE_paving (Poly Haven CC0 concrete_pavement_02)", BlendMode.SOFTLIGHT, 32, false);
    addMask(L4, chW);

    var hazeRGB = (VARIANT == "daylight") ? [196, 208, 224] : [58, 74, 112];
    var L5 = fillLayer("05_AERIAL_HAZE (depth-masked)", hazeRGB, BlendMode.NORMAL, (VARIANT == "daylight") ? 30 : 11);
    addMask(L5, chD);
    var gradeRGB = (VARIANT == "daylight") ? [255, 238, 214] : [150, 176, 232];
    fillLayer("06_GRADE_" + VARIANT, gradeRGB, BlendMode.SOFTLIGHT, (VARIANT == "daylight") ? 14 : 12);
    var L7 = fillLayer("07_VIGNETTE", [0, 0, 0], BlendMode.MULTIPLY, (VARIANT == "daylight") ? 22 : 24);
    addMask(L7, chV);

    var S = stampVisible("08_STAMP_visible (curves, unsharp)");
    doc.activeLayer = S;
    S.adjustCurves([[0, 0], [64, 57], [190, 198], [255, 255]]);
    S.applyUnSharpMask(32, 1.1, 2);
    log("curves + unsharp applied");
    var soft = S.duplicate();
    soft.name = "09_LENS_EDGE_SOFTNESS";
    soft.applyGaussianBlur(1.4);
    soft.opacity = 70;
    addMask(soft, chV);

    var G = fillLayer("10_FILM_GRAIN", [128, 128, 128], BlendMode.OVERLAY, 34);
    G.applyAddNoise(3.2, NoiseDistribution.GAUSSIAN, true);
    log("grain applied");

    var psd = new PhotoshopSaveOptions();
    psd.layers = true; psd.embedColorProfile = true; psd.alphaChannels = true;
    var psdFile = F("G002_" + VARIANT + "_FINAL.psd");
    doc.saveAs(psdFile, psd, true, Extension.LOWERCASE);
    log("saved PSD: " + psdFile.fsName);

    var flat = doc.duplicate();
    flat.flatten();
    var png = new PNGSaveOptions(); png.interlaced = false; png.compression = 6;
    var pngFile = F("G002_" + VARIANT + "_FINAL.png");
    flat.saveAs(pngFile, png, true, Extension.LOWERCASE);
    flat.close(SaveOptions.DONOTSAVECHANGES);
    log("saved PNG: " + pngFile.fsName);
    log("layers: " + doc.layers.length + "  channels: " + doc.channels.length);
    doc.close(SaveOptions.DONOTSAVECHANGES);
    log("PHOTOSHOP_FINISH_OK " + app.version);
} catch (e) {
    log("ERROR: " + e + " (line " + e.line + ")");
}
var lf = F("ps_log_" + VARIANT + ".txt");
lf.encoding = "UTF-8"; lf.open("w"); lf.write(LOG.join("\n")); lf.close();
LOG.join(" | ");
