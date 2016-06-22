# open interface with gtk
# interface needs:
#   threshold sliders
#       threshold sliders should trigger a re-threshold on the snapped image to allow maybe getting better edges after the fact
#
#   text entry for name of person
#   SNAP button
#   Save button with nonce incremented
#   live preview and silhoette preview.. twice... one for them on the seccond screen, one for me...
#   maybe send to vinyl cutter menu with size etc
#       serial preview for debugging...
#       have buttons for manual vinyl cutter control
#
# Backend stuff
#   open camera
#   grab frame
#   pull out biggest blob
#   2 color the image
#   blit to live views
#   respond to snap button by holding current snapshot in preview area
#   respond to save by saving the 2 color image to disk
#       also save full color image, so that manual editing can be done in inkscape or gimp if needed
#   respond to send to vinyl by:
#       converting to svg somehow, probably by calling external inkscape or something
#       using external inkcut to generate vinyl cutter commands
#       sending to vinyl cutter over serial

#   several processes should run indepenedenly and communicate with queues
#   camera process grabs image
#   processing queue recieves image and detects blobs etc, and outputs results
#   display queue grabs images and updates screen
#   the prototype of this is the "LineControl" from process_test.py

import Tkinter as tk
import ttk
import datetime

def update_clock():
    clock_value.set(datetime.datetime.now().strftime('%A %b %d  %I:%M:%S %p'))
    root.after(1000,update_clock)

root = tk.Tk(  )
if __name__ == '__main__':

    clock_value = tk.StringVar(value= 'clock')
    update_clock()
    ttk.Label(root, textvariable=clock_value ,borderwidth=1).grid(row=0,column=0)
    
    root.mainloop(  )