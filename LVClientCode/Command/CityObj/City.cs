using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
namespace LVClient.Command.CityObj 
{
    public class City 
	{
        public int id;
        public string name;
        public int size = 0;
        public int x;
        public int y;
		public int parentID;
        public Command.CityObj.Building[] AllBuilding;
        public Command.CityObj.MilitaryGeneral[] MilitaryGeneral;
		public Command.CityObj.CivilGeneral[] CivilGeneral;

		public int cntbuild = 0;
        public ArrayList generalupsikhi;
        public CityTask citytask;
		
		public static bool isBuildAll = false;
		public static bool isDowndAll = false;

		public static bool isBuyRes = true;		// mua tai nguyen neu can
		public static long goldSafe= 5000000;		// mua tai nguyen neu can



        public static LVClient.Command.CityObj.City[] AllCity;

        public City(int id, string name, int x, int y, int size) 
		{
            this.id = id;
            this.name = name;
            this.x = x;
            this.y = y;
            this.size = size;
        }
		public City(int id, string name, int x, int y, int size, int parentID)
		{
			this.id = id;
			this.name = name;
			this.x = x;
			this.y = y;
            this.size = size;
			this.parentID = parentID;
		}
        public override string ToString() 
		{
            return this.name;
        }
        public static bool Canbuild(int id){
            foreach(City cty in City.AllCity){
                if(cty.id == id){
                    return cty.citytask.CanBuild;
                }
            }
            return false;
        }
        public static bool Cantp(int id) {
            foreach (City cty in City.AllCity) {
                if (cty.id == id) {
                    return cty.citytask.Cantp;
                }
            }
            return false;
        }
        public static bool Canupgrade(int id) {
            foreach (City cty in City.AllCity) {
                if (cty.id == id) {
                    return cty.citytask.Canupgrade;
                }
            }
            return false;
        }
    }
}
