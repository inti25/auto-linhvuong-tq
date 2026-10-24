using System;
using System.Collections.Generic;
using System.Text;
using System.IO;

namespace LVClient.Common {
    class config {
        public static string[] SELLRESOURCE = null;
        public static string[] BUYRESOURCE = null;
        public static string[] UPDATEBUILDING = null;
        public static string[] DELBUILDING = null;
        public static string[] THAOPHAT = null;
        public static string[] UPGRADE = null;
        public static string[] VANCHUYEN = null;
        public static string[] ADDNK = null;
        public static string[] WEPON = null;
        public static void load(string filename){
            SELLRESOURCE = null;
            BUYRESOURCE = null;
            UPDATEBUILDING = null;
            DELBUILDING = null;
            THAOPHAT = null;
            UPGRADE = null;
            VANCHUYEN = null;
            ADDNK = null;
            WEPON = null;
            try {
                FileStream f = new FileStream(filename, FileMode.Open);
                byte[] data = new byte[10000];
                f.Read(data, 0, (int)f.Length);
                string fdata = UTF8Encoding.UTF8.GetString(data, 0, (int)f.Length);
                f.Close();
                string[] sall = fdata.Split(new char[]{'/'});
                for (int i = 0; i < sall.Length; i++) {
                    string[] item = sall[i].Split(new char[] { ',' });
                    if (item[0] == "SELLRESOURCE") {
                        SELLRESOURCE = item;
                    }
                    if (item[0] == "BUYRESOURCE") {
                        BUYRESOURCE = item;
                    }
                    if (item[0] == "UPDATEBUILDING") {
                        UPDATEBUILDING = item;
                    }
                    if (item[0] == "DELBUILDING") {
                        DELBUILDING = item;
                    }
                    if (item[0] == "THAOPHAT") {
                        THAOPHAT = item;
                    }
                    if (item[0] == "UPGRADE") {
                        UPGRADE = item;
                    }
                    if (item[0] == "VANCHUYEN") {
                        VANCHUYEN = item;
                    }
                    if (item[0] == "ADDNK") {
                        ADDNK = item;
                    }
                    if (item[0] == "WEPON") {
                        WEPON = item;
                    }
                }
            } catch (Exception ex) {

            }
        }
    }
}
