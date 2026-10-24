using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
	public class BanTaiNguyenObj
	{
		public int timetoruninminute = 1;
		public bool SalesOff = true;
		public commonInfo LUA = new commonInfo(LVClient.LVThread.BUYRES.RESOURCETYPE.LUA);
		public commonInfo GO = new commonInfo(LVClient.LVThread.BUYRES.RESOURCETYPE.GO);
		public commonInfo SAT = new commonInfo(LVClient.LVThread.BUYRES.RESOURCETYPE.SAT);
		public commonInfo DA = new commonInfo(LVClient.LVThread.BUYRES.RESOURCETYPE.DA);
		public cityInfo_[] CityInfo;

		public void NewCityInfo(int count)
		{
			CityInfo = new cityInfo_[count];
		}

		
		public  class commonInfo
		{
			public bool BanCoDinh = true;
			public int SoLuongBan		= 1000;
			public int SoLuongAnToan	= 500;
			//public bool GiaCoDinh		= true;
			public int LoaiBan = 2;		// 1: co dinh, 2: theo gia trung binh, 3: theo gia thap nhat
			public bool CongThucNhan	= false;		
			public double GiaTri		= 0;
			public int ResType;		  // 1: lua, 2:
			
			
			public commonInfo(int restype)
			{
				this.ResType = restype;
			}
		}

		public  class cityInfo_
		{
			public int CityId;
			public string CityName;
			public bool BanLua;
			public bool BanGo;
			public bool BanSat;
			public bool BanDa;
		}

		public static class LOAIBAN
		{
			public  const int THEOGIACODINH = 1;
			public   const int THEOGIATRUNGBINH = 2;
			public   const int THEOGIATHAPNHAT = 3;
		}

		
	}
}
