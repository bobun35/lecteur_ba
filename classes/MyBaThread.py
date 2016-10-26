import sys
import os
if os.environ['HOME_BA'] not in sys.path:
    try:
        sys.path.append(os.environ['HOME_BA'])
    except:
        print("error in HOME_BA environment variable")
import subprocess
import threading
#import youtube_dl
import subprocess
import time
import datetime
import pickle
from time import sleep, mktime, strptime
import logging, logging.config
import env_variables
from classes.MyPlaylist import PlaylistElement
from classes.MySlideList import Slide
from classes.MyBaList import Ba
from omxplayer import OMXPlayer
from dbus.exceptions import DBusException
logging.config.dictConfig(env_variables.LOGGING)
logging.getLogger('omxplayer').setLevel(logging.CRITICAL)
logging.getLogger('dbus').setLevel(logging.CRITICAL)


class BaOmxThread(threading.Thread):
    """
    Thread qui fait tourner les ba et slides en boucle sur un player omx
    """

    def __init__(self, ba_file_list, timer_in_seconds=None):
        super(BaOmxThread, self).__init__()
        self.ba_file_list = ba_file_list
        self.timer_in_seconds = timer_in_seconds
        self.name = "etoile_cinema"
        #self.stoprequest = threading.Event()

    def _display_slide(self, slide_path, display_duration):
        """ 
        function that displays the slide using feh command during 
        display_duration number of timer_in_seconds
        """
        try:
            logging.info("slide montre: %s" % slide_path)
            command = "export DISPLAY=:0;/usr/bin/feh --no-fehbg --bg-scale '" + slide_path +"'"
            return_code = subprocess.call(command, shell=True)
            if return_code == 0:
                sleep(display_duration)
            else:
                raise RuntimeError
        except Exception as e:
            logging.error("command is:%s" % command)
            logging.error("display slide return code: %i" % return_code)
            logging.error('image display failed: %s' % str(e))

    def _play_ba(self, ba_path, stop, time_status, save_file):
        """
        function qui lance une bande-annonce dans omx player
        """
        player = OMXPlayer(ba_path, args=['-o', 'hdmi', '-b', '--no-osd'])
        player.play()

        # affichage d'un ecran noir pour ne pas voir l'ecran de la ba precedente
        # brievement avant le changement d'ecran
        self._display_slide(env_variables.black_image, 1)
        logging.info("ba: %s, status: %s" % (ba_path, player.playback_status()))                        

        # tant que la ba n'est pas fini ou stoppee, on attend
        while True:
            try:
                if player.playback_status() == "Playing" and stop is False and time_status is False:
                    sleep(1)
                    stop = pickle.load(open( save_file, "rb" ))
                    #logging.info("%s, %s, %s" % (player.playback_status(),stop, time_status))  
                else:
                    logging.warn("before player quit")
                    player.quit()
                    # sortie boucle while
                    break
            except DBusException:
                logging.warn("dbus exception")
                # cette exception est levee a la fin de la ba, sortie du while
                break
        return stop

    def run(self):
        time_status = False
        stop = False
        save_file = os.path.join(env_variables.home_ba, 'save.p')
        pickle.dump(stop, open( save_file, "wb" ))
        logging.info("in run method")
    
        # tant que l'on a pas appuye sur "stopper les ba", on continue !
        env_variables.lock.acquire()
        # ajouter un check de la valeur de timer
        timeout = time.time() + self.timer_in_seconds

        while stop is False and time_status is False:
            
            for track in self.ba_file_list:

                # sortie de la boucle for si stop = True
                if stop or time_status:
                    break

                if isinstance(track, PlaylistElement):

                    # diffusion de la ba dans l'omx player
                    stop = self._play_ba(track.ba_path, stop, time_status, save_file)

                    # affichage du slide avec dates de diffusion entre deux bande-annonces
                    if stop is False:
                        self._display_slide(track.slide_path, env_variables.temps_entre_2_ba)

                elif isinstance(track, Slide):
                    # affichage de la promo
                    self._display_slide(track.filepath, env_variables.temps_affichage_promo)

                elif isinstance(track, Ba):
                    # lancement de la ba seule e.g. carte fidelite dans l'omx player
                    stop = self._play_ba(track.filepath, stop, time_status, save_file)

                time_status = time.time() > timeout

        env_variables.lock.release()

        if time_status is True:
            subprocess.call(['sudo', 'shutdown', '-h', 'now'])