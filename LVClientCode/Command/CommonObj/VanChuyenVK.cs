using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Command.CommonObj
{
	public class VanChuyenVK
	{
		public long id; 
		public int ThanhChuyenDiID;
		public int ThanhChuyenDenID;
		public int LoaiVuKhiID;
		public int TongSoLuongChuyen;
		public int SoLuongChuyenMoiLan;

		public int DaChuyenDuoc;

		public VanChuyenVK()
		{
		}

		public VanChuyenVK(int ThanhChuyenDiID, int ThanhChuyenDenID, int LoaiVuKhiID, int TongSoLuongChuyen, int soluongchuyenmoilan)
		{
			id = DateTime.Now.Ticks;
			this.ThanhChuyenDiID = ThanhChuyenDiID;
			this.ThanhChuyenDenID = ThanhChuyenDenID;
			this.LoaiVuKhiID = LoaiVuKhiID;
			this.TongSoLuongChuyen = TongSoLuongChuyen;
			this.SoLuongChuyenMoiLan = soluongchuyenmoilan;
		}
		public override string ToString()
		{
			

			//string str = "Chuyển " + LVClient.Common.Wepons.GetWeponName(LoaiVuKhiID) + " từ " + Command.City.GetCityByID(ThanhChuyenDiID);
			//str += " đến " + Command.City.GetCityByID(ThanhChuyenDenID) + " (" + DaChuyenDuoc + "/" + SoLuongPhaiChuyen + ")";


			string str = "Chuyển từ " + Command.City.GetCityByID(ThanhChuyenDiID) + " đến " + Command.City.GetCityByID(ThanhChuyenDenID);
			str += ": " + LVClient.Common.Wepons.GetWeponName(LoaiVuKhiID) + " (" + DaChuyenDuoc + "/" + TongSoLuongChuyen + ")";
			return str;
		}

	}
}
