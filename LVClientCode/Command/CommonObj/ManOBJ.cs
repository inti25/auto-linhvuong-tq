using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
    using System;

    public class ManOBJ
    {
        public int ManID;
        public string ManName;
        public int MapID;
        public int X;
        public int Y;

        public int CompareTo(object obj)
        {
            if (!(obj is ManOBJ))
            {
                throw new ArgumentException("object is not a Temperature");
            }
            ManOBJ nobj = (ManOBJ) obj;
            return this.ManID.CompareTo(nobj.ManID);
        }
    }
}

