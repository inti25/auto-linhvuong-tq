using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace LVClient.Common 
{
    public class WarFunc 
	{
		public const int TRANHINHAMOUNT = 6;
        //Trận hình
        //public static int[] 
        //trùy câu ky hạc ngư
        //1 2 3 4 5
        public static int[] Attack = new int[] { 0, 1, 2, 3, 4, 5 };
		public static int[] AntiAttack = new int[] { 0, 4, 5, 1, 2, 3 };				// trả về 1.2

		//public static int[] TranHinhAttack	= new int[] { 0, 1, 2, 3, 4, 5 };
		public static int[] TranHinhYeu	= new int[] { 0, 3, 4, 5, 1, 2 };				// trả về 0.8 
		//public static int[] TranHinhYeu		= new int[] { 0, 4, 5, 1, 2, 3 };

		public static double[,] ArrayValue = 
			{
				{0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
				{0.0, 1.0, 1.1, 1.2, 0.8, 0.9},
				{0.0, 0.9, 1.0, 1.1, 1.2, 0.8},
				{0.0, 0.8, 0.9, 1.0, 1.1, 1.2},
				{0.0, 1.2, 0.8, 0.9, 1.0, 1.1},
				{0.0, 1.1, 1.2, 0.8, 0.9, 1.0},
			};

		
		private static Hashtable MuuKeTrongChienTruong = new Hashtable();
		private static Hashtable MuuKeTrongChienTruongDescription = new Hashtable();
		static WarFunc()
		{

			MuuKeTrongChienTruong.Add(0, "Không dùng");
			MuuKeTrongChienTruong.Add(96, "Hủy bỏ trạng thái");
			MuuKeTrongChienTruong.Add(92, "Kim thiền thoát xác");
			MuuKeTrongChienTruong.Add(93, "Phản khách vi chủ");
			MuuKeTrongChienTruong.Add(95,	"Cầm tặc cầm vương");
			MuuKeTrongChienTruong.Add(94, "Quan môn tróc tặc");


			MuuKeTrongChienTruongDescription.Add(0, "");
			MuuKeTrongChienTruongDescription.Add(96, "Sử dụng đối với quân đội mình trong chiến trường, sau khi sử dụng quân đội lập tức giải trừ trạng thái, khôi phục lại bình thường.");
			MuuKeTrongChienTruongDescription.Add(92, "Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ trực tiếp rút khỏi chiến đấu, sĩ khí không bị tổn thất.");
			MuuKeTrongChienTruongDescription.Add(93, "Sử dụng đối với quân đội của mình trong chiến trường. Sau khi sử dụng quân đội sẽ được ưu tiên công kích trong hiệp kế tiếp.");
			MuuKeTrongChienTruongDescription.Add(95, "Sử dụng đối với quân đội của mình trong chiến trường, sau khi sử dụng nếu quân đội chiến thắng trong hiệp kế tiếp thì phe địch sẽ giảm một nửa sĩ khí.");
			MuuKeTrongChienTruongDescription.Add(94, "Sử dụng đối với phe địch trong chiến trường,sau khi sử dụng quân đội đó sẽ không thể chấp hành lệnh rút quân trong 3 hiệp liên tiếp (trừ phi đối phương sử dụng Kim thiền thoát xác).");

		}
		
		/// <summary>
		/// Lấy trận hình khắc trận hình hiện tại (trả về trận hình 1.2)
		/// </summary>
		/// <param name="tranhinh">ID Trận hình</param>
		/// <returns>Trận hình khắc (= trận hình 1.2)</returns>
		public static int GetTranHinhKhac(int tranhinh)
		{
			return AntiAttack[tranhinh];	// TranHinhKhac[tranhinh];
		}

		/// <summary>
		/// Lấy trận hình yếu trận hình hiện tại (trả về trận hình 0.8)
		/// </summary>
		/// <param name="tranhinh"></param>
		/// <returns></returns>
		public static int GetTranHinhYeu(int tranhinh)
		{
			return TranHinhYeu[tranhinh];	// TranHinhKhac[tranhinh];
		}

		public static class TRANHINH
		{
			public const int TuyChon = 0;
			public const int TruyHinh = 1;
			public const int CauHinh = 2;
			public const int KiHinh = 3;
			public const int HangDuc = 4;
			public const int NguLan = 5;   			
		}

		public static class PHUONGTHUCTANCONG
		{
			public const int TuyChon = 0;
			public const int TanCongPhoThong = 1;
			public const int DonChien = 2;
			public const int PhongNgu = 3;
			public const int RutLui = 4;
			public const int DotKich = 10;
			public const int ManhCong = 11;
			public const int ThuyCong = 12;
			public const int HoaTien =13;
			public const int PhanKich=14;

		}

		public class MUUKETRONGCHIENTRUONG
		{
			public const int KhongDung = 0;
			public const int HuyBoTrangThai = 96;	//	Hủy bỏ trạng thái	
			public const int KimThienThoatXac = 92;	 // Kim thiền thoát xác
			public const int PhanKhachViChu = 93;	//Phản khách vi chủ
			public const int CamTacVuong = 95;	//Cầm tặc cầm vương
			public const int QuanMonTrocTac = 94;	//Quan môn tróc tặc
		
		}

		public static string GetMuuKeTrongChienTruongName(int muukeid)
		{
			if (MuuKeTrongChienTruong.Contains(muukeid)) return MuuKeTrongChienTruong[muukeid].ToString();
			else return "Unknown";
		}

		public static string GetMuuKeTrongChienTruongDescription(int muukeid)
		{
			if (MuuKeTrongChienTruongDescription.Contains(muukeid)) return MuuKeTrongChienTruongDescription[muukeid].ToString();
			else return "";
		}

    }
}
