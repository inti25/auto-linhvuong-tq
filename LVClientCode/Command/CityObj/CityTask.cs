using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
namespace LVClient.Command.CityObj {
    public class CityTask {
        public bool CanBuild = false;
        public bool Canupgrade = false;
        public bool Canmove = false;
        public bool Cantp = false;
        public bool CanMBC = false;
        public CityTask(int countbuild, int tech, int task, int mcb) {
            if (countbuild < 3) {
                CanBuild = true;
            }
            if (tech == 0) {
                Canupgrade = true;
            }
            if (task == 0) {
                Cantp = true;
            }
            if (mcb < 4300 && mcb>0) {
                CanMBC = true;
                System.Media.SoundPlayer mp = new System.Media.SoundPlayer();
                mp.SoundLocation = @"alert.wav";
            }
        }
    }
}
