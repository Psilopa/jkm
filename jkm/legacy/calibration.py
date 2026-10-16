# TODO: NEED REIMPLEMENTATION
"""
Tools for finding, analyzing and redrawing calibration data from images.

Calibration data (poorly) supported:
- scales

Missing: 
- greyscale calibration panels
- colour calibration panels
"""

import cv2
import numpy as np
#import matplotlib.pyplot as plt
import jkm.tools as tools
#import detect_ruler as dr
#import cProfile

def get_edge(img,width=100,edge=0): # Get a slice along an edge (0=bottom)
    return img[-width:-1,:]

def split_edge(img,n_parts = 10): # Returns the edge in 10 parts
    im = img.copy()
    if img.shape[0] < img.shape[1]: # After this first dim is always the longer dim
        im = cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)
    imgp = []    
    step = int(im.shape[0]/n_parts)
    for x in range(0,n_parts*step,step):
        sect = im[x:x+step,:]
        imgp.append(sect)
    return imgp        

def optimize_ppu(list_of_values):
    """Logic: skip values that are roughly harmonics of the smallest value,
    then take a median"""
    x = []
    tol = 0.05
    fmin = min(list_of_values)
    for f in list_of_values:
        for h in [1,2,3,4]:  # Harmonic factors
            ratio = abs(1-(f/h)/fmin)
            if  ratio < tol:
                x.append(f/h)
                break
    return np.median(np.array(x))
    
def extract_pixels_per_ruler_unit(img,optimize=False):
    """Assumes rules near edge and ticks perpendicular to edge!

    Returns a list of pix-per-ruler estimates (potentially with float values!).

    You can use optimize_ppu() to convert the list to a single value.
    """
    # Resize,  greyscale
    fx = fy = 1
    img_gr = cv2.resize(img,(0,0),fx=fx,fy=fy)
    img_gr = cv2.cvtColor(img_gr,cv2.COLOR_RGB2GRAY)
    edge_width = int(max(img_gr.shape)/10)
    # Find edges
    # Currently gets only one edge (=lower edge)
    edge = get_edge(img_gr, edge_width, 0)
    values = []
    for sect in split_edge(edge)[1:-1:2]: # Every second element long this edge, except end elements       
#        sectb = cv2.GaussianBlur(sect, (11,11), 10) 
#        sectc = cv2.addWeighted(sect, 1.0 + 3.0, sectb, -3.0, 0) # Unsharp masking
        
        # Find wavelength of ruler pattern (pixels/tick)
        pix_per_u = dr.find_pix_per_tick_CSDF(sect, optimize)
        values.append(pix_per_u)        
    return values

def draw_scalebar(img,pix_per_unit,height_in_px=45, unit="mm",lenincm = 2, pattern="bw", place="cu", print_text="cm"):
    # needs to find empty spot!
    black = (0,0,0) 
    white = (255,255,255)
    fill = -1
    if unit.lower()=='mm': wpix = int(lenincm*10*pix_per_unit)
    else: wpix = int(lenincm*pix_per_unit)
    pw = wpix//lenincm # part width (TODO: generalize for scale lengths 0,1,2,...)
    outimg = img.copy()    
    if place=="cu": # upper, center
        x0 = img.shape[1]//2 - wpix//2
        y0 = img.shape[0]//50
    else: # No other options supported currently
        x0 = img.shape[1]//2 - wpix//2
        y0 = img.shape[0]//50
    if pattern=="bw": # Half black, half white
        p1 = (x0, y0)
        p2 = (x0 + pw, y0 + height_in_px)
        cv2.rectangle(outimg,p1,p2,black,fill)
        p1 = (x0 + pw, y0) 
        p2 = (x0 + 2*pw, y0 + height_in_px)
        cv2.rectangle(outimg,p1,p2,white,fill)
    if print_text:
        fontScale = height_in_px/20
        font = cv2.FONT_HERSHEY_DUPLEX
        line= 3
        p = (x0 + wpix + 10, y0 + height_in_px)
        yup = 10
        cv2.putText(outimg, "0", (x0,y0-yup), font, color=black, fontScale=fontScale, thickness=line)
        cv2.putText(outimg, "1", (x0+pw,y0-yup), font, color=black, fontScale=fontScale, thickness=line)
        cv2.putText(outimg, "2", (x0+2*pw,y0-yup), font, color=black, fontScale=fontScale, thickness=line)
        cv2.putText(outimg, print_text, p, font, color=black, fontScale=fontScale, thickness=line)
    return outimg






def mainfunc():
    img = tools.load_img(r"Z:\jkmulticam\testout\GK.9317\GK.9317_20191205_14h34m17s\GK.9317_20191205_14h34m17s_labelcam.jpg")
#    img = tools.load_img(r"F:\F.201633\Image001.tif")
#    img = tools.load_img(r"testdata/croptests/specimen1.jpg")
    x = extract_pixels_per_ruler_unit(img,optimize=True)
    print("ppu values", x)
    if x is None:
        print("Nothing found")
    else:
        ppu = optimize_ppu(x)
        outimg = draw_scalebar(img,ppu,print_text="cm")    
        cv2.imwrite(r"testout.jpg",outimg)

if __name__ == '__main__':
    mainfunc()
