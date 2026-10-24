using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.BuildObj {
    class UpdateBuildingInfo {
        public int NextLevel;
        public int FoodNeed;
        public int WoodNeed;
        public int IronNeed;
        public int StoneNeed;
        public int GoldNeed;
        public UpdateBuildingInfo(int NextLevel, int FoodNeed, int WoodNeed, int IronNeed, int StoneNeed, int GoldNeed) {
            this.NextLevel = NextLevel;
            this.FoodNeed = FoodNeed;
            this.WoodNeed = WoodNeed;
            this.IronNeed = IronNeed;
            this.StoneNeed = StoneNeed;
            this.GoldNeed = GoldNeed;
        }
    }
}
