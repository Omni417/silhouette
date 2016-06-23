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
from multiprocessing import Process, Queue, Pipe
import pygame
import pygame.camera
import pygame.image
from pygame.locals import *
import os
from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageChops, ImageFont
import time

SIZE = (640,480)



def update_clock():
    clock_value.set(datetime.datetime.now().strftime('%A %b %d  %I:%M:%S %p'))
    root.after(1000,update_clock)

# a tkinter object with internal queues and processing
class CameraPipeline(object):

    def __init__(self,root,live1):
        #save frames that will be updated with images or data
        self.root = root
        #self.live1 = live1
        #self.live2 = live2
        #self.preview1 = preview1
        #self.preview2 = preview2
        #self.control_book = control_book
        #self.image_label = ttk.Label(master = self.live1)
        #self.image_label.grid(row=0,column=0)

        # set up asynchronous queues to pipe image data to the appropriate routines
        self.camera_image_queue = Queue()
        self.image_processing_controls_queue = Queue()
        self.image_processing_queue = Queue()
        self.image_output_queue = Queue()

        # set up triggers to update actions
        #self.camera_threshold.trace_variable('w', self.save_threshold)

        #set up interface

        self.display = ttk.LabelFrame(master=live1, text='camera')
        self.display.grid(column=0, row=0)

        self.image_display = tk.Label(master=self.display)
        self.image_display.grid(column=0, row=0)


        #self.display = ttk.LabelFrame(master=live1, text='Live view')
        #self.display.grid(column=0, row=0)
        #self.image_display = tk.Label(master=self.live1)
        #self.image_display.grid(column=0, row=0)
        #self.control_display = tk.Frame(master=control_book)

        self.vision_process = Process(target=self.process_image)
        self.vision_process.daemon = True
        self.vision_process.start()

        self.start_camera()  # cam_process started here
        self.root.after(20, self.display_image)

    def start_camera(self):
        clist = pygame.camera.list_cameras()
        print clist
        camnum = 1 #get the second camera
        self.camera = pygame.camera.Camera(clist[camnum], SIZE, 'RGB')
        self.camera.start()
        self.camera.get_image()
        self.root.after(200, self.set_exposure)
        self.cam_process = Process(target=self.cam_to_queue)
        self.cam_process.daemon = True
        self.cam_process.start()
        return

    def cam_to_queue(self):
        while True:
            if self.camera_image_queue.empty():  # send at most 1 image to be processed
                snapshot = self.camera.get_image()
                #print 'got frame'
                self.camera_image_queue.put(pygame.image.tostring(snapshot, 'RGB'))

    def set_exposure(self):
        #prevents exposure from changing
        #os.system('v4l2-ctl -d {} -c exposure_absolute=8'.format(self.camdev))
        pass

    def process_image(self):
        DISPLAY_SIZE = SIZE
        output = {}
        while True:
            if self.image_processing_queue.empty():
                #print "process_image_loop"
                input = self.camera_image_queue.get(True)  # will block until image is ready
                image = Image.frombytes('RGB', SIZE, input)
                small2 = image.filter(ImageFilter.SMOOTH)

                output['image'] = image.tostring()
                output['image_mode'] = 'RGB'
                output['image_size'] = DISPLAY_SIZE
                self.image_processing_queue.put(output)

    def display_image(self):

        # try to display image,
        try:
            #print 'trying to get frame'
            data = self.image_processing_queue.get(True)
            a = Image.frombytes(data['image_mode'], data['image_size'], data['image'])
            self.live_image = ImageTk.PhotoImage(image=a)
            #print "got an image, and attempting to display it"
            #self.image_display.configure(image=z)
            #self.image_display._image_cache = z
            self.image_label = ttk.Label(photo=self.live_image,master=self.live1)
            self.image_label.grid(row=0,column=0)
        except:
            pass

        self.root.after(20, self.display_image)

    def display_image(self):

        # try to display image,
        try:
            #print 'trying to get frame'
            data = self.image_processing_queue.get(False)
            a = Image.frombytes(data['image_mode'], data['image_size'], data['image'])
            #b = a.resize((320, 240))
            z = ImageTk.PhotoImage(image=a)
            self.image_display.configure(image=z)
            self.image_display._image_cache = z
        except:
            pass

        self.root.after(20, self.display_image)


    def stop_camera(self):
        try:
            self.cam_process.terminate()
            time.sleep(0.1)
            if self.cam_process.is_alive():
                print "killing camera process"
                os.system('kill -9 {}'.format(self.cam_process.pid))  # process won't terminate normally
            self.camera.stop()
            #LineControl.cameras_taken.remove(self.camdev)
        except:
            pass

    def kill(self):
        self.stop_camera()
        self.vision_process.terminate()
        if self.vision_process.is_alive():
            print "had to kill process"
            os.system('kill -9 {}'.format(self.vision_process.pid))  # process won't terminate normally

def exit_handler():
    pygame.quit()
    print 'terminating'
    camera.kill()
    root.quit()
    root.destroy()

root = tk.Tk(  )
if __name__ == '__main__':

    pygame.init()
    pygame.camera.init()

    clock_value = tk.StringVar(value= 'clock')
    update_clock()
    ttk.Label(root, textvariable=clock_value ,borderwidth=1).grid(row=0,column=0)

    video_window = tk.Frame(master=root,height=480,width=640)
    video_window.grid(column=0, row=1)

    camera = CameraPipeline(root,video_window)
    root.mainloop(  )