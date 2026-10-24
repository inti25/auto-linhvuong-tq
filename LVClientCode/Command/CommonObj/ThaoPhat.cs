using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj {
    class ThaoPhat {
        public int id;
        public string name;
        public static ThaoPhat[] AllNhiemVu;
        public ThaoPhat(int id, string name) 
		{
            this.id = id;
            this.name = name;
        }
        public override string ToString() 
		{
            return name;
        }

		public static string GetNhiemVuName(int nhiemvuID)
		{
			string name= "unknow";
			ThaoPhat tp;
			for (int i = 0; i < AllNhiemVu.Length; i++)
			{
				tp = (ThaoPhat)AllNhiemVu[i];
				if (nhiemvuID == tp.id) return tp.name;

			}

			return name;


		}
	}
}
