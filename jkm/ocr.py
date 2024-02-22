import logging
import pytesseract
import numpy as np
import cv2
import jkm.tools
#from pathlib import Path
import time, sys

log = logging.getLogger() # Overwrite if needed
_net = None

# DEFAULT SETUP
#eastfile = r"Z:/EAST/frozen_east_text_detection.pb"
min_confidence = 0.9
padding = 1.5 # Increase in text box size as a factor (pre-merging)
postpadding = 1.2
proc_size = 3*320 # Width of image used (should be a multiple of 32)
ocr_max_width = 3000
def_timeout = 10
def_lang = "eng"

def load_neural_net(fn):
    # TODO: add error handling
    log.debug("Loading neural net text detector (EAST) from %s ..." % fn)
    try:
        net = cv2.dnn.readNet(fn)
        log.debug("EAST text detector loaded.")
    except cv2.error as msg: 
        log.critical(f"Loading text detection neural net (EAST) failed: {msg}")
        sys.exit()
    return net

def intersection(a, b):
    startX = max( min(a[0], a[2]), min(b[0], b[2]) )
    startY = max( min(a[1], a[3]), min(b[1], b[3]) )
    endX = min( max(a[0], a[2]), max(b[0], b[2]) )
    endY = min( max(a[1], a[3]), max(b[1], b[3]) )
    if startX < endX and startY < endY: return True
    else: return False

def boundingbox(a, b): 
    startX = min( a[0], b[0] )
    startY = min( a[1], b[1] )
    endX = max( a[2], b[2] )
    endY = max( a[3], b[3] )
    return (startX, startY, endX, endY, b[4]) # Copies over rotation angle of b

def group_rects(rects): # Primitive implementation!
    len_in = len(rects)
    if len_in == 0: return ()
    if len_in == 1: return rects
    remaining = rects.copy() # remaining rectangles
    first_discrete = False
    while not first_discrete and len(remaining) >1:
        r0 = remaining[0]
        first_discrete = True
        for i in range(1,len(remaining)): # Look for intersecting rectangles
            if intersection(r0,remaining[i]):
                remaining.insert(1,boundingbox(r0,remaining[i]))
                remaining.pop(0) 
                remaining.remove(remaining[i]) 
                first_discrete = False
                break
    # First element is now unique
    len_out = len(remaining)
    if len_in == len_out: return remaining
    # Move first to last and repeat
    remaining.append(remaining.pop(0))
    return group_rects(remaining)
    
def _pad(x1,y1,x2,y2,pad = 1.2): # Pad as a factor
    w = max((x2-x1) * pad, 0) # New width
    h = max((y2-y1) * pad, 0) # New height
    halfpadx = 0.5*(pad-1)*w
    halfpady = 0.5*(pad-1)*h
    x1f = int( max(0,x1-halfpadx) )
    x2f = int( x2+halfpadx )
    y1f = int( max(0,y1-halfpady) )
    y2f = int( y2+halfpady )
    return (x1f,y1f,x2f,y2f)

def find_text_rects(img, nnfn = eastfile, max_textareas = 10):
    "nnfn = neural net file name"
    # Uses a (module) global neural net _net
    # Resize to a square
#    orig = img.copy()
    global _net
    if _net is None: _net = load_neural_net(nnfn)
    (h0, w0) = img.shape[:2]
    (W, H) = (proc_size, proc_size)
    rW = w0 / float(W)
    rH = h0 / float(H)
    img = cv2.resize(img, (W, H))    
    layerNames = [ # DNN output fields
	"feature_fusion/Conv_7/Sigmoid",
	"feature_fusion/concat_3"]
    # Last argument : mean values for each RGB channel
    blob = cv2.dnn.blobFromImage(img, 1.0, (W, H),(123.68, 116.78, 103.94))
    _net.setInput(blob)
    log.debug("Detecting text elements")
    (scores, geometry) = _net.forward(layerNames)
    (numRows, numCols) = scores.shape[2:4]
    rects = []
    confidences = []
    for y in range(numRows):
        scoresData = scores[0, 0, y]
        xData0 = geometry[0, 0, y]
        xData1 = geometry[0, 1, y]
        xData2 = geometry[0, 2, y]
        xData3 = geometry[0, 3, y]
        anglesData = geometry[0, 4, y] 
        for x in range(0, numCols):
                if scoresData[x] < min_confidence: continue
                # compute the offset factor as our resulting feature maps will
                # be 4x smaller than the input image
                (offsetX, offsetY) = (x*4, y*4)
                # extract the rotation angle for the prediction and then
                # compute the sin and cosine
                angle = anglesData[x]
                cos = np.cos(angle)
                sin = np.sin(angle)
#                print("found rect with angle %f" % math.degrees(angle))
                # DImensions of the bounding box
                hr = xData0[x] + xData2[x]
                wr = xData1[x] + xData3[x]
                endX = int(offsetX + (cos * xData1[x]) + (sin * xData2[x]))
                endY = int(offsetY - (sin * xData1[x]) + (cos * xData2[x]))
                startX = int(endX - wr)
                startY = int(endY - hr)
                newrect = _pad(startX, startY, endX, endY, padding)
                newrect = list(newrect)
                newrect.append(angle)
                rects.append(newrect)
                confidences.append(scoresData[x])
    log.debug("... Found %i individual areas" % len(rects))
    out = []
#    clr = (0, 255, 0)
    log.debug("Grouping text areas near each other")
    max_textareas = 10
    grouped = group_rects(rects)
    maxlen = min(max_textareas, len(grouped))
    if len(grouped) > max_textareas:
        log.debug(f"Too many text areas ({len(grouped)}), processing only first {max_textareas}")
    for (x1, y1, x2, y2,rot) in grouped[0:maxlen]:
        x1 = int(max(x1,0) * rW)
        x2 = int(min(x2,W) * rW)
        y1 = int(max(y1,0) * rH)
        y2 = int(min(y2,H) * rH)
        # Pad this box
        x1,y1,x2,y2 = _pad(x1,y1,x2,y2,postpadding)
        out.append((x1,y1,x2,y2, rot))
#        cv2.rectangle(orig, (x1,y1), (x2,y2), clr, 2)
#    cv2.imshow("Text Detection", orig)
#    cv2.waitKey(0)
    log.debug("... Found %i groups" % len(out))
    return out

def ocr(rect, timeout=def_timeout,lang=def_lang,fdir=None):
    "OCR text from a given rectangle (image array"
    increasecontast = True
    if increasecontast: rect = jkm.tools.gammacorrect(rect,3)
    try:
        start_time = time.time()
        txtf = pytesseract.image_to_string(rect,timeout=timeout,lang=lang)
        elapsed_time = time.time() - start_time
        log.debug("Time spent in OCR process %.2f seconds" % elapsed_time)
    except pytesseract.TesseractError as err:
        log.info("Error in OCR: {err}%s")    
        return ""
    return txtf
