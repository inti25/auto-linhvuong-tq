using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
	public class DieuPhaiTuong
	{
		public long  ID;
		public int generalid;
		public string generalname;
		public int cityID;
		public string cityname;
		public int generaltype;		//1: quan van, 2: quan vo
		public int tasktype;	// 1: dao mo, 2: loi dai
		public int loidailevel;
		public int X;
		public int Y;
		public int timetoruninmilisecond;
		public string desc;
		//public static DIEUPHAITUONG_ DIEUPHAITUONG = new DIEUPHAITUONG_();

		public DieuPhaiTuong()
		{
			this.ID = DateTime.Now.Ticks;
			
		}

		public long GetID
		{
			get { return ID;}
		}

		public string GetDesc
		{
			get { return desc; } 
		}

		public static class GENERALTYPE
		{
			public const int QuanVan = 1;
			public const int QuanVo = 2;
		}
		public static class TASKTYPE
		{
			public const int DaoMo = 1;
			public const int LoiDai = 2;
		}
		
	}
	
}
