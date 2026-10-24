using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CityObj 
{
    public class Building : IComparable 
	{
        //0,2,"Tường thành",29,0,0
        public int pid;
        public int gid;
        public string name;
        public int level;
        public int tab=-99;
		public bool isUp = false;		// nang cap
		public bool isDown = false;		// ha cap cap

        public Building(int pid, int gid, string name, int level)
		{
            this.pid = pid;
            this.gid = gid;
            this.name = name;
            this.level = level;
        }
        public override string ToString() 
		{
            return name;
        }
        public int CompareTo(object obj) 
		{
            if (obj is Building) 
			{
                Building temp = (Building)obj;

                return this.level.CompareTo(temp.level);
            }
            throw new ArgumentException("object is not a Temperature");
        }
    }
    
}
