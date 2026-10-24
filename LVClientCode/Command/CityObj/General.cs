using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace LVClient.Command.CityObj
{
	public class General : IComparable 
	{
		public int GeneralId;
		public string GeneralName;
		public string GeneralHistroryName;

		public int CityID;				// thanh/trai cua tuong do
		public string CityName;
		
		/// <summary>
		/// Trạng thái tướng bình thường, đang xuất chinh ...
		/// </summary>
		public int GeneralStatus;		//0: binh thuong; 16: dang xuat chinh
		public int Generaltype;		// 1: van, 2 vo

		/// <summary>
		/// Chức tước, nhàn rỗi, mưu sỹ, thái thu ...
		/// </summary>
		public int ChucTuoc;		//0: nhan roi, 3: muu sy, 1: thai thu, 2: quan su
		public int Level;
		public int MucTrungThanh;

		public int TheLucHienTai;
		public int TongTheLuc;


		public int DiemCongConLai;


		public override string ToString()
		{
			/*
			string st = "";

			st = CityName + " - " + GeneralName;

			if (GeneralHistroryName != "")
				st += "(" + GeneralHistroryName + ")";

			if (ChucTuoc != 0)
				st += " - " + GetChucTuocName(ChucTuoc);

			if (GeneralStatus != 0)
				st  += " - " + GetTrangThaiName(GeneralStatus);




			return st;
			 * */

			return GeneralName;
		}

		public struct TrangThaiTuong
		{
			public const int Binhthuong		= 0;
			public const int TrongThuong	= 1;
			public const int TriThuong		= 2;
			public const int XuatChinh		= 16;
			public const int DiChiVien		= 17;
			public const int LoiDai			= 18;
			public const int DieuPhai		= 21;
			public const int NhiemVu		= 24; 
			public const int ChiVien = 29;

		}

		public static string GetTrangThaiName(int status)
		{
			string name = "Unknow";
			switch (status)
			{
				case 0:
					name = "Bình thường";
					break;

				case 1:
					name = "Trọng thương";
					break;

				case 2:
					name = "Trị thương";
					break;

				case 16:
					name = "Xuất chinh";
					break;

				case 17:
					name = "Đi Chi viện";
					break;

				case 18:
					name = "Lôi đài";
					break;
				
				case 21:
					name = "Điều phái";
					break;

				case 24:
					name = "Nhiệm vụ";
					break;
				
				case 29:
					name = "Chi viện";
					break;

				


				default:
					name = "Unknow";
					break;
			}

			return name;
		}

		/// <summary>
		/// Trạng thái quân đội hỗn loạn, thiếu kỉ luật
		/// </summary>
		public struct TrangThaiQuanDoi
		{
			public const int BinhThuong = 0;
			public const int HonLoan = 1;
			public const int SoHai = 4;	
			public const int ThieuKiLuat = 3;
		}

		/// <summary>
		/// Lấy tên trạng thái quân đội (hỗn loạn, thiếu kỉ luật)
		/// </summary>
		/// <param name="trangthaiID"></param>
		/// <returns>Tên trạng thái</returns>
		public static string GetTrangThaiQuanDoiName(int trangthaiID)
		{
			string name = "Unknow";
			switch (trangthaiID)
			{
				case TrangThaiQuanDoi.BinhThuong:
					name = "Bình thường";
					break;

				case TrangThaiQuanDoi.HonLoan:
					name = "Hỗn loạn";
					break;

				case TrangThaiQuanDoi.ThieuKiLuat:
					name = "Thiếu kỉ luật";
					break;

				case TrangThaiQuanDoi.SoHai:
					name = "Sợ hãi";
					break;

				default:
					name = "Unknow";
					break;
			}

			return name;

		}

		/// <summary>
		/// Lấy hệ số giảm của trạng thái quân đội, Bình thường =1, hỗn loạn = 0.5, thiếu kỉ luật = 0.8
		/// </summary>
		/// <param name="trangthaiID"></param>
		/// <returns>Trả về hệ số, hỗn loạn =0.1, bình thường=1 </returns>
		public static double GetHeSoTrangThaiQuanDoi(int trangthaiID)
		{
			double rate= 1;
			switch (trangthaiID)
			{
				case TrangThaiQuanDoi.BinhThuong:
					rate = 1;
					break;

				case TrangThaiQuanDoi.HonLoan:
					rate = 0.1;
					break;

				case TrangThaiQuanDoi.ThieuKiLuat:
					rate = 0.8;
					break;

				case TrangThaiQuanDoi.SoHai:
					rate = 0.8;
					break;

				default:
					rate = 0.9;
					break;
			}

			return rate;

		}


		/// <summary>
		/// Chức tước của quan văn (Thái thú, Quân sư ...)
		/// </summary>
		public struct ChucTuocTuong
		{
			public const int NhanRoi = 0;
			public const int ThaiThu = 1;
			public const int QuanSu = 2;
			public const int MuuSy = 3;
		}
		public static string GetChucTuocName(int chuctuocid)
		{
			string name = "Unknow";
			switch (chuctuocid)
			{
				case 0:
					name = "Nhàn rỗi";
					break;

				case 1:
					name = "Thái thú";
					break;

				case 2:
					name = "Quân Sư";
					break;

				case 3:
					name = "Mưu Sỹ";
					break;

				default:
					name = "Unknow";
					break;
			}

			return name;
		}


	
		// sắp xếp theo ID
		public virtual int CompareTo(object obj)
		{
			if (obj is General)
			{
				General temp = (General)obj;

				if (this.CityID != temp.CityID)
					return this.CityID.CompareTo(temp.CityID);
				else
					if (this.Generaltype != temp.Generaltype)
						return this.Generaltype.CompareTo(temp.Generaltype);
					else
						return this.GeneralId.CompareTo(temp.GeneralId);
			}
			throw new ArgumentException("object is not a Temperature");
		}



     

        /// <summary>
        /// Kiểm tra xem tướng đang có đánh nhau hay đang đi không.
        /// Nếu có thì add vào chiến trường
        /// </summary>
        /// <param name="militaryGeneral"></param>
        /// <param name="sotuongminhdanh1tuongdich"></param>
        /// <returns>true: đang bận, false: không bận</returns>
        public static bool isTuongDangBusy(Command.CityObj.MilitaryGeneral militaryGeneral, int sotuongminhdanh1tuongdich)
        {
            ArrayList tmp = new ArrayList();
            tmp.Add(militaryGeneral);
            return  isTuongDangBusy(tmp, sotuongminhdanh1tuongdich);
        }
		/// <summary>
		/// Kiểm tra xem tướng đang có đánh nhau hay đang đi không.
		/// Nếu có thì add vào chiến trường
		/// </summary>
		/// <param name="callmanifo">List of Command.CityObj.MilitaryGeneral</param>
		/// <returns>true: đang bận, false: không bận</returns>
		public static bool isTuongDangBusy(ArrayList militaryGeneral, int sotuongminhdanh1tuongdich)
		{
			int cityid = 0;
			int genid = 0;
			Command.CityObj.MilitaryGeneral callmanobj;
			ArrayList geninfo;

			bool ret = false;

			Hashtable result;
			ArrayList temp;

			try
			{
                int genIDtmp = 0;
				for (int genidx = 0; genidx < militaryGeneral.Count; genidx++)
				{

					callmanobj = (Command.CityObj.MilitaryGeneral)militaryGeneral[genidx];

                    if (callmanobj.GeneralId == genIDtmp) continue;
                    genIDtmp = callmanobj.GeneralId;

					cityid = callmanobj.CityID;
                    LVClient.Command.CityObj.City cityByID = LVClient.Command.City.GetCityByID(cityid);

					string cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
					LVClient.Command.City.SwitchCitySlow(cityid);



					int status;
					int time;		//s
					int battleid;

					string para;
					// check xem co đang đánh nhau khong
					if (cityid > 0)                             // thien thanh gid=69
                        if (cityByID.size >3)
                            para = "gid=69&pid=-1&tab=1&tid=0";
                        else
						    para = "gid=16&pid=-1&tab=1&tid=0";
					else
						para = "gid=19&pid=-1&tab=1&tid=" + cityid;

					Hashtable result1 = LVClient.Command.Build.Execute(2, para, true, cookies);
					if (result1 != null && result1["ret"].ToString() == "0")
					{
						ArrayList battle = (ArrayList)result1["battle"];
						for (int ii = 0; ii < battle.Count; ii++)
						{
							temp = (ArrayList)battle[ii];
							battleid = int.Parse(temp[0].ToString());

							// lay thong tin chien truong
							para = "lBattleID=" + battleid;
							result = LVClient.Command.Common.Execute(4, para, true, cookies);
							if (result != null)
							{
								// check xem tướng mình có đang đánh nhau không
								ArrayList myside = (ArrayList)result["myside"];
								for (int i = 0; i < myside.Count; i++)
								{
									temp = (ArrayList)myside[0];
									status = int.Parse(temp[0].ToString());
									genid = int.Parse(temp[13].ToString());
									battleid = int.Parse(result["battle_id"].ToString());
									if (callmanobj.GeneralId == genid)
									{
										//SetText("Tướng " + callmanobj.GeneralName + " đang đi...");
										//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
										//LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, 0, Callmanobj.SoTuongMinhDanh1TuongDich, 300, Callmanobj.PhuongThucTanCongID, Callmanobj.PhuongThucChonMucTieuID);
										LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, 0, sotuongminhdanh1tuongdich, militaryGeneral);
										ret = true;
										break;
										//return true;
									}

								}
							}// end if (result != null)						
						} // end 					for (int i = 0; i < battle.Count; i++)

					}


					// kiem tra xem co dang di khong
					para = "tid=0";
					if (cityid > 0)
						para = "tid=0";
					else
						para = "tid=" + cityid;


					result = LVClient.Command.Common.Execute(40, para, true, cookies);
					//result = LVClient.Command.City.GetCityTask(cookies);
					if (result != null)
					{
						ArrayList gotobat = (ArrayList)result["goto"];
						for (int i = 0; i < gotobat.Count; i++)
						{
							ArrayList oneGotobat = (ArrayList)gotobat[i];
							status = int.Parse(oneGotobat[1].ToString());       // sai, cos the la 2 
							time = int.Parse(oneGotobat[13].ToString());		//s
							genid = int.Parse(((ArrayList)(((ArrayList)oneGotobat[8])[0]))[0].ToString());
							battleid = int.Parse(oneGotobat[4].ToString());         // nếu là đánh địa tinh thì id=0, kiểm tra [1]=14: địa tinh; =1: đánh man
                            if (callmanobj.GeneralId != genid) continue;

                            if (int.Parse(oneGotobat[1].ToString()) == 14)      // DDiaj tinh
                            {
                                int x = int.Parse(oneGotobat[6].ToString());
                                int y = int.Parse(oneGotobat[7].ToString());
                                // laays thong tin battleID cua dia tinh
                                Hashtable tmp = Command.Common.Execute(98, "DestX=" + x + "&DestY=" + y, true);
                                if (tmp != null && tmp["ret"].ToString() == "0")
                                {
                                    battleid = int.Parse(tmp["npc_id"].ToString());
                                }

                            }


							if (status != 0)			// Đang di hoặc đang về thao phat	 1: dang di, 2: dang danh, 3: đang trở về
							{
								//SetText("Tướng " + callmanobj.GeneralName + " đang đi...");

								if (status == 2) time = 0;
								//if (battleid != 0 && (status == 1 || status == 2))
                                if (battleid != 0 )
                                {

									//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
									//LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, time, Callmanobj.SoTuongMinhDanh1TuongDich, 300, Callmanobj.PhuongThucTanCongID, Callmanobj.PhuongThucChonMucTieuID);
									LVClient.LVThread.AUTOFIGHTING.startBattle(battleid, time, sotuongminhdanh1tuongdich, militaryGeneral);

								}

								ret = true;
								break;
								//return true;
							}
						}

					}
				}
				return ret;

			}
			catch (Exception ex)
			{
				return ret;
			}

		}


	}
}
