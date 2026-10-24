using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace LVClient.Common
{
	
	public class Ruong
	{
		private static Hashtable htRuong = new Hashtable();

		static Ruong()
		{																		
			htRuong.Add(1,"Dân sinh bảo nang");
			htRuong.Add(2,"Cổ khí bảo nang");
			htRuong.Add(3,"Thần võ bảo nang");
			htRuong.Add(5, "Phúc khoáng bảo nang");
			htRuong.Add(6, "Dân sinh bảo phiên");
			htRuong.Add(7,"Cổ khí bảo phiên");
			htRuong.Add(8,"Thần võ bảo phiên");
			htRuong.Add(11,"Dân sinh bảo hạp");
			htRuong.Add(12,"Cổ khí bảo hạp");
			htRuong.Add(13,"Thần vũ bảo hạp");
			htRuong.Add(16,"Dân sinh bảo độc");
			htRuong.Add(17,"Cổ khí bảo độc");
			htRuong.Add(21,"Thần võ bảo độc");
			htRuong.Add(23, "Phúc Khoán bảo độc"); 
			htRuong.Add(24, "Dân sinh bảo đỉnh");
			htRuong.Add(25,"Cổ khí bảo đỉnh");
			htRuong.Add(26, "Thần vũ bảo đỉnh");
			htRuong.Add(35, "Bạch kim tư nguyên lễ hạp");
			htRuong.Add(41, "Trứng");
			htRuong.Add(44, "Quân giới bổ cấp rương");
			htRuong.Add(46, "Trung cấp man tướng rương");
			htRuong.Add(49, "Pháo hoa loại lớn");
			htRuong.Add(50, "Pháo hoa loại nhỏ");
			htRuong.Add(53, "Ngự tứ bảo hạp");

		}

		public static string GetRuongName(int id)
		{
			
				if (!htRuong.ContainsKey(id))
				{
					return "Unknown";
				}
				string ret = htRuong[id].ToString();
				if (ret == null || ret == "")
					ret = "Unknown";

				return ret;
			
		}

	}

}
