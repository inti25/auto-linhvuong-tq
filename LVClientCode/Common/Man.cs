using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace LVClient.Common
{
   

    public class Man
    {
        private static Hashtable man = new Hashtable();

        static Man()
        {
            man.Add(1, "Uy quốc");
            man.Add(2, "Tiên Ti");
            man.Add(3, "Ô hoàn");
            man.Add(4, "Sơn việt");
            man.Add(5, "Khương để");
            man.Add(6, "Mạnh hoạch");
            man.Add(7, "Hung nô");
            man.Add(0x65, "Đạo quân lương");
            man.Add(0xc9, "Thần thú");
        }

        public static string GetManName(int id)
        {
            if (!man.ContainsKey(id))
            {
                return "Unknown";
            }
            string str = man[id].ToString();
            switch (str)
            {
                case null:
                case "":
                    str = "Unknown";
                    break;
            }
            return str;
        }
    }
}

