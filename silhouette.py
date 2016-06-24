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

RUNNING = True

def update_clock():
    clock_value.set(datetime.datetime.now().strftime('%A %b %d  %I:%M:%S %p'))
    root.after(1000,update_clock)

# a tkinter object with internal queues and processing
class CameraPipeline(object):

    def __init__(self,root):
        #save frames that will be updated with images or data
        self.second = tk.Toplevel()
        self.second.wm_title("Mirror")
        self.root = root
        self.display = tk.Frame(master=root)
        self.display.grid(column=0, row=0)
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


        self.live_mirror = tk.Label(master=self.second)
        self.live_mirror.grid(column=1, row=0)
        self.preview_mirror = tk.Label(master=self.second)
        self.preview_mirror.grid(column=0, row=0)
        self.live = tk.Label(master=self.display)
        self.live.grid(column=1, row=0)
        self.preview = tk.Label(master=self.display)
        self.preview.grid(column=0, row=0)

        #setup thresholding variables
        self.tR=tk.IntVar()
        self.tG=tk.IntVar()
        self.tB=tk.IntVar()
        self.tW=tk.IntVar()
        self.tR.trace_variable('w', self.send_image_processing_controls)
        self.tG.trace_variable('w', self.send_image_processing_controls)
        self.tB.trace_variable('w', self.send_image_processing_controls)
        self.tW.trace_variable('w', self.send_image_processing_controls)
        self.send_image_processing_controls()

        self.filename=tk.StringVar()
        self.nonce=tk.StringVar()
        self.nonce.set("0")

        self.tcontrol = ttk.LabelFrame(master=self.display,text="Threshold")
        self.tcontrol.grid(row=1,column=0)
        tk.Label(master=self.tcontrol,text='Red').grid(row=0,column=0)
        tk.Label(master=self.tcontrol,textvariable=self.tR,width=3).grid(row=0,column=1)
        tk.Scale(master=self.tcontrol,orient=tk.HORIZONTAL, from_=0,to=255,variable=self.tR,length=255,resolution=1.0,showvalue=0,takefocus=1).grid(row=0,column=2)
        tk.Label(master=self.tcontrol,text='Green').grid(row=1,column=0)
        tk.Label(master=self.tcontrol,textvariable=self.tG,width=3).grid(row=1,column=1)
        tk.Scale(master=self.tcontrol,orient=tk.HORIZONTAL, from_=0,to=255,variable=self.tG,length=255,resolution=1.0,showvalue=0,takefocus=1).grid(row=1,column=2)
        tk.Label(master=self.tcontrol,text='Blue').grid(row=2,column=0)
        tk.Label(master=self.tcontrol,textvariable=self.tB,width=3).grid(row=2,column=1)
        tk.Scale(master=self.tcontrol,orient=tk.HORIZONTAL, from_=0,to=255,variable=self.tB,length=255,resolution=1.0,showvalue=0,takefocus=1).grid(row=2,column=2)
        tk.Label(master=self.tcontrol,text='Width').grid(row=3,column=0)
        tk.Label(master=self.tcontrol,textvariable=self.tW,width=3).grid(row=3,column=1)
        tk.Scale(master=self.tcontrol,orient=tk.HORIZONTAL, from_=0,to=255,variable=self.tW,length=255,resolution=1.0,showvalue=0,takefocus=1).grid(row=3,column=2)
        tk.Entry(master=self.tcontrol,textvariable = self.filename).grid(row=4,column=0)
        tk.Entry(master=self.tcontrol,textvariable = self.nonce).grid(row=4,column=2)
        tk.Button(master=self.tcontrol,text='save',command=self.saveimage).grid(row=4,column=3)


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

    def send_image_processing_controls(self, name=None, index=None, mode=None):
        controls = {}
        controls['tr'] = int(self.tR.get())
        controls['tg'] = int(self.tG.get())
        controls['tb'] = int(self.tB.get())
        controls['tw'] = int(self.tW.get())
        self.image_processing_controls_queue.put(controls)

    def saveimage(self):
        snapshot = self.camera.get_image()
        dest=snapshot.copy()
        filename = self.filename.get()
        number = int(self.nonce.get())
        tr = int(self.tR.get())
        tg = int(self.tG.get())
        tb = int(self.tB.get())
        tw = int(self.tW.get())

        pygame.transform.threshold(dest,snapshot,(tr,tg,tb),(tw,tw,tw),(255,255,255),1)
        pygame.image.save(dest,"{}_{}.png".format(filename,number))
        pygame.image.save(snapshot,"{}_{}_raw.png".format(filename,number))
        pygame.image.save(dest,"/var/www/html/current.png")

        self.nonce.set("{}".format(number+1))


    def start_camera(self):
        clist = pygame.camera.list_cameras()
        #print clist
        camnum = 0 #get the second camera
        self.camera = pygame.camera.Camera(clist[camnum], SIZE, 'RGB')
        self.camera.start()
        self.camera.get_image()
        self.root.after(200, self.set_exposure)
        self.cam_process = Process(target=self.cam_to_queue)
        self.cam_process.daemon = True
        self.cam_process.start()
        return

    def cam_to_queue(self):
        self.snapshot = pygame.surface.Surface(SIZE)

        while True:
            output = {}
            if RUNNING is False:
                break


            if self.camera_image_queue.empty():  # send at most 1 image to be processed
                self.snapshot = self.camera.get_image()
                #print "queue size is {}".format(self.camera_image_queue.qsize())
                #self.sil = snapshot
                #print 'got frame'
                #pygame.transform.threshold(self.sil,snapshot,(0,200,0),(30,60,30),(0,0,0),2)

                output['snapshot']=pygame.image.tostring(self.snapshot, 'RGB')
                #output['sil']=pygame.image.tostring(snapshot, 'RGB')
                self.camera_image_queue.put(output)
                time.sleep(.05)

    def set_exposure(self):
        #prevents exposure from changing
        #os.system('v4l2-ctl -d {} -c exposure_absolute=8'.format(self.camdev))
        pass

    def process_image(self):
        DISPLAY_SIZE = SIZE
        output = {}
        controls = self.image_processing_controls_queue.get()
        tr = controls['tr']
        tg = controls['tg']
        tb = controls['tb']
        tw = controls['tw']
        #print 'got controls'
        while True:
            try:
                controls = self.image_processing_controls_queue.get(False)
                #print 'got controls'
                tr = controls['tr']
                tg = controls['tg']
                tb = controls['tb']
                tw = controls['tw']
            except:
                pass
            if self.image_processing_queue.empty():
                #print "process_image_loop"
                input = self.camera_image_queue.get(True)  # will block until image is ready
                #print "queue size is {}".format(self.camera_image_queue.qsize())
                #image = Image.frombytes('RGB', SIZE, input['snapshot'])
                #small2 = image.filter(ImageFilter.SMOOTH)

                #output['image'] = image.tostring()
                #output['image_mode'] = 'RGB'
                #output['image_size'] = DISPLAY_SIZE

                siltmp= pygame.image.frombuffer(input['snapshot'],SIZE,'RGB')
                dest=siltmp.copy()

                #pygame.transform.threshold(self.sil,tmp,(self.TR,self.TG,self.TB),(w,w,w),(0,0,0),2)
                pygame.transform.threshold(dest,siltmp,(tr,tg,tb),(tw,tw,tw),(255,255,255),1)
                #print "thresholding with {} threshold at ({},{},{})".format(tw,tr,tg,tb)
                #pygame.transform.threshold(self.sil,tmp,(0,255,0),(50,50,50),(127,127,127))
                #self.sil = pygame.transform.flip(tmp,0,1)
                output['sil'] = pygame.image.tostring(dest, 'RGB')
                #print len(output['sil'])
                #print "done silhouetting"

                self.image_processing_queue.put(output)



    def display_image(self):

        # try to display image,
        try:
            #print 'trying to get frame'
            data = self.image_processing_queue.get(True)
            #a = Image.frombytes('RGB', SIZE, data['sil'])
            #b=a.transform(SIZE,Image.EXTENT,(640,0,0,480))
            #b = a.resize((320, 240))
            #z = ImageTk.PhotoImage(image=a)
            #mirror = ImageTk.PhotoImage(image=b)

            #self.live.configure(image=mirror)
            #self.live._image_cache = mirror

            #self.live_mirror.configure(image=mirror)
            #self.live_mirror.image_cache = mirror

            #self.preview.configure(image=z)
            #self.preview._image_cache = z
            #self.preview_mirror.configure(image=mirror)
            #self.preview_mirror.image_cache = mirror


            #print "getting silhouette"
            sila = Image.frombytes('RGB', SIZE, data['sil'])
            #silz = ImageTk.PhotoImage(image=sila)
            #print "1"
            silb = sila.transform(SIZE,Image.EXTENT,(640,0,0,480))
            #print "2"
            #print "3"
            silm = ImageTk.PhotoImage(image=silb)
            sill = silb.resize((SIZE[0]*2,SIZE[1]*2))
            silll = ImageTk.PhotoImage(image=sill)
            #print "built the silouettes"

            self.preview.configure(image=silm)
            self.preview._image_cache = silm
            self.preview_mirror.configure(image=silll)
            self.preview_mirror.image_cache = silll



            #check to see if silhouette exists in data...
            #if it does, update silhouette frames






        except:
            pass
        if RUNNING is True:
            self.root.after(20, self.display_image)


    def stop_camera(self):
        try:
            self.cam_process.terminate()
            time.sleep(0.1)
            if self.cam_process.is_alive():
                #print "killing camera process"
                os.system('kill -9 {}'.format(self.cam_process.pid))  # process won't terminate normally
            self.camera.stop()
            #LineControl.cameras_taken.remove(self.camdev)
        except:
            pass

    def kill(self):
        self.vision_process.terminate()
        time.sleep(0.2)
        if self.vision_process.is_alive():
            #print "had to kill vision process"
            os.system('kill -9 {}'.format(self.vision_process.pid))  # process won't terminate normally
        self.stop_camera()

def exit_handler():
    global RUNNING
    RUNNING = False
    time.sleep(.2)
    pygame.quit()
    print 'terminating'
    camera.kill()
    root.quit()
    root.destroy()

root = tk.Tk(  )
if __name__ == '__main__':

    pygame.init()
    pygame.camera.init()

    #clock_value = tk.StringVar(value= 'clock')
    #update_clock()
    #ttk.Label(root, textvariable=clock_value ,borderwidth=1).grid(row=0,column=0)


    camera = CameraPipeline(root)
    root.protocol("WM_DELETE_WINDOW", exit_handler)
    root.mainloop()