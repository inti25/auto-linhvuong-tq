using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
	public class MuaTaiNguyenObj
	{

		public long VangAnToan = 10000000;
		public double TimeToRunInMinute = 1;
		public bool MuaTheoDonViKho = false;
		public double GiaTri = 100;

		public cityInfo_[] CityInfo;

		public void newCityInfo(int count)
		{
			CityInfo = new cityInfo_[count];
		}

		
		public class cityInfo_
		{
			public int CityId;
			public string CityName;
			public bool MuaLua;
			public bool MuaGo;
			public bool MuaSat;
			public bool MuaDa;
			public int Vitridangmua = 0;  // dung de danh dau mua loai tai nguyen nao
		}
	}
}
