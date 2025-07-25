#!/usr/bin/env python

import rospy
from std_msgs.msg import Int8, Empty, Bool
from std_srvs.srv import Trigger, TriggerResponse
from buzzer.srv import PlayMelody, PlayMelodyResponse
import threading
import time
import mido
import os
import rospkg

class MelodyPlayerNode:
    def __init__(self):
        self.pub_note = rospy.Publisher('note', Int8, queue_size=10)
        self.pub_hb = rospy.Publisher('heartbeat', Empty, queue_size=10)
        self.pub_status = rospy.Publisher('playing_status', Bool, queue_size=1)

        self.playing_event = threading.Event()
        self.player_thread = None

        rospy.Timer(rospy.Duration(0.1), self.heartbeater)
        rospy.Service('play_melody', PlayMelody, self.handle_start)
        rospy.Service('stop_melody', Trigger, self.handle_stop)

        self.melody_map = rospy.get_param('/melody/melody_map', {})
        if not self.melody_map:
            rospy.logwarn("melody_map parameter is empty or missing. Please define it in your launch file.")

    def heartbeater(self, _):
        self.pub_hb.publish(Empty())

    def play_midi(self, filepath, loop):
        midi_file = mido.MidiFile(filepath)
        self.pub_status.publish(True)

        while self.playing_event.is_set() and not rospy.is_shutdown():
            for msg in midi_file.play():
                if not self.playing_event.is_set():
                    self.pub_note.publish(-1)
                    self.pub_status.publish(False)
                    return
                if msg.type == 'note_on':
                    self.pub_note.publish(msg.note)
                elif msg.type == 'note_off':
                    self.pub_note.publish(-1)
            if not loop:
                self.playing_event.clear()
                break

        self.pub_note.publish(-1)
        self.pub_status.publish(False)

    def handle_start(self, req):
        if self.playing_event.is_set():
            return PlayMelodyResponse(success=False, message="Already playing")

        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path('buzzer')
        filename = self.melody_map.get(str(req.melody_id), self.melody_map["0"])
        filepath = os.path.join(pkg_path, 'resources', filename)
        self.playing_event.set()

        self.player_thread = threading.Thread(target=self.play_midi, args=(filepath, req.loop))
        self.player_thread.start()

        return PlayMelodyResponse(success=True, message="Started")

    def handle_stop(self, _):
        if self.playing_event.is_set():
            self.playing_event.clear()
            self.player_thread.join()
            return TriggerResponse(success=True, message="Stopped")
        return TriggerResponse(success=False, message="Nothing was playing")

def main():
    rospy.init_node('melody_player', anonymous=True)
    node = MelodyPlayerNode()
    rospy.loginfo("MelodyPlayerNode initialized")
    rospy.spin()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass

