using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread 
{
    public class THAOPHAT 
	{
        delegate void SetTextCallback(string text);
        private Thread InThread;
		private string threadID;
		public bool IsRun = false;
		private Label Message;

		private ArrayList TuongDiThaoPhat; //GeneralThaoPhat array
		private int Sleep = 60000;
		private int CityID;
		//private LVClient.Command.CityObj.MilitaryGeneral[] gArray = null;
		private int Batleid = 0;
		private int SoLuongTuongDanh1Dich = 1;
		//private LVClient.Command.CityObj.MilitaryGeneral gobj;
		/*
		private int g1;
        private int g2;
        private int g3;
        private int g4;
        private int g5;
        private int idnhiemvu;
        private bool Upsikhi = false;
        private int Id = 0;
      
       
		private int sikhimin = 50;
		private bool tubienchequan = false;
		private int soluongquanmin= 20000;


		
		//private int TimeToChangeArray = 250;	// thời gian đổi trận hình
	
		private int TimeDoiTranHinh = 250;
		private int PhuongThucTanCong = 0;
		private int PhuongThucChonMucTieu;

		

		

		LVClient.Common.GeneralThaoPhat GeneralThaoPhat; 
		*/


		public THAOPHAT(Label lbl) 
		{
            Message = lbl;
        }
       /* public void GetParameter(int idcity,int g1,int g2,int g3,int g4,int g5,int idnhiemvu, bool upsikhi, int sleep, int sikhimin, int soluongquanmin, bool tubienchequan) 
		{
			string cookies;
            //if (!IsRun) 
			{

                //Cookies = new string[500];
                this.Sleep = sleep;

                //Xay dung cookies
                Id = idcity;
                this.g1 = g1;
                this.g2 = g2;
                this.g3 = g3;
                this.g4 = g4;
                this.g5 = g5;
                Upsikhi = upsikhi;
                this.idnhiemvu = idnhiemvu;
				this.sikhimin = sikhimin;
				this.tubienchequan = tubienchequan;
				this.soluongquanmin = soluongquanmin;
            }
        }
		*/

		/*public void GetParameter(LVClient.Common.GeneralThaoPhat generalThaoPhat, int sleep)
		{
			string cookies;
			//if (!IsRun) 
			{

				this.GeneralThaoPhat = generalThaoPhat;
				this.Sleep = sleep;

				//Xay dung cookies
				Id = generalThaoPhat.cityid;
				this.g1 = generalThaoPhat.general1;
				this.g2 = generalThaoPhat.general2;
				this.g3 = generalThaoPhat.general3;
				this.g4 = generalThaoPhat.general4;
				this.g5 = generalThaoPhat.general5;
				Upsikhi = generalThaoPhat.tuupsikhi;
				this.idnhiemvu = generalThaoPhat.nhiemvuid;
				this.sikhimin = generalThaoPhat.sikhimin;
				this.tubienchequan = generalThaoPhat.tubienchequan;
				this.soluongquanmin = generalThaoPhat.soluongquanmin;
				this.PhuongThucTanCong = generalThaoPhat.phuonthuctancong;
				this.PhuongThucChonMucTieu = generalThaoPhat.phuongthucchonmuctieu;
			}
		}
		*/

		//LVClient.Common.GeneralThaoPhat
		/// <summary>
		/// Nhận các thông số cho thảo phạt
		/// </summary>
		/// <param name="General"> Hashtable[generalID,Common.GeneralThaoPhat] </param>
		/// <param name="sleep">time to check (ms)</param>
		public void GetParameter(ArrayList General, int sleep)
		{
			
			//if (!IsRun) 
			{

				this.TuongDiThaoPhat = General;
				this.Sleep = sleep;
				this.CityID = ((Common.GeneralThaoPhat)General[0]).CityID;

				/*
				//Xay dung cookies
				Id = generalThaoPhat.cityid;
				this.g1 = generalThaoPhat.general1;
				this.g2 = generalThaoPhat.general2;
				this.g3 = generalThaoPhat.general3;
				this.g4 = generalThaoPhat.general4;
				this.g5 = generalThaoPhat.general5;
				Upsikhi = generalThaoPhat.tuupsikhi;
				this.idnhiemvu = generalThaoPhat.nhiemvuid;
				this.sikhimin = generalThaoPhat.sikhimin;
				this.tubienchequan = generalThaoPhat.tubienchequan;
				this.soluongquanmin = generalThaoPhat.soluongquanmin;
				this.PhuongThucTanCong = generalThaoPhat.phuonthuctancong;
				this.PhuongThucChonMucTieu = generalThaoPhat.phuongthucchonmuctieu;
				 */ 
			}
		}
		
		private void mainprocess()
		{
			LVClient.Command.CityObj.MilitaryGeneral geninfo;
			//bool skok = true;
			//bool luongquanok = false;
			string cookies;
			System.Collections.Hashtable result = null;
			//int sk =100;
			
			int[] g = new  int[5];
			int idnhiemvu;

			try
			{
				Message.ForeColor = System.Drawing.Color.Red;
				SetText("Đang chạy (0%)");
				cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(CityID);
				LVClient.Command.City.SwitchCitySlow(CityID);

				result = Command.City.GetCityTask(cookies);
				if (result != null)
				{
					ArrayList task = (ArrayList)result["task"];
					int status = int.Parse(task[2].ToString());
					int time = int.Parse(task[3].ToString());


					if (status != 0)			// Đang di hoặc đang về thao phat	 1: dang di, 2: dang danh, 3: đang trở về
					{
						if (status == 2) time = 0;
						if (status == 1 || status == 2)
						{
							//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
							LVClient.LVThread.AUTOFIGHTING.startBattle(Batleid, time, SoLuongTuongDanh1Dich, TuongDiThaoPhat);
						}
						return;
					}
				}

				

				Common.GeneralThaoPhat GeneralThaoPhat=null;
				bool canrun = true;
				LVClient.Command.CityObj.MilitaryGeneral gArray = null;

				for (int idx = 0; idx < this.TuongDiThaoPhat.Count; idx++)
				{
					GeneralThaoPhat = (Common.GeneralThaoPhat)TuongDiThaoPhat[idx];
					g[idx] = GeneralThaoPhat.GeneralId;

					// bo xung them quan
					if (GeneralThaoPhat.TuBienCheQuan)
					{
						/*
						Common.BienChe oneBienche;
						for (int i = 0; i < LVClient.frmmain.ListBienChe.Count; i++)
						{
							oneBienche = (Common.BienChe)LVClient.frmmain.ListBienChe[i];
							if (oneBienche.cityid == CityID && GeneralThaoPhat.GeneralId == oneBienche.generalid)
							{
								SetText("Biên chế quân cho " + GeneralThaoPhat.GeneralName + "...");
								Common.BienCheQuan.BienChe(oneBienche.cityid, oneBienche.generalid, oneBienche.bobinhamount, oneBienche.kybinhamount, oneBienche.cungthuamount, oneBienche.xemount);
								break;
							}
						}
						 */

						SetText("Biên chế quân cho " + GeneralThaoPhat.GeneralName + "...");
						Common.BienCheQuan.BienChe(GeneralThaoPhat.CityID, GeneralThaoPhat.GeneralId, GeneralThaoPhat.BienCheBoBinhAmount,
											GeneralThaoPhat.BienCheKyBinhAmount, GeneralThaoPhat.BienCheCungThuAmount, 
											GeneralThaoPhat.BienCheXeAmount);

					}

					/*
					if (Upsikhi)
					{
						if (Id > 0)
							Command.Build.SelectBuilding(Id, 16, cookies);
						else
							Command.Build.SelectBuilding(Id, 19, cookies);
					}
					*/

					// check quaan so
					gArray = Command.Common.GetGeneralInforInLuyenBinh(CityID,GeneralThaoPhat.GeneralId);
					if (gArray == null)
					{
						canrun = false;
						continue;
					}
					if (gArray.Military.Bobinh[0] + gArray.Military.KyBinh[0] + gArray.Military.CungThu[0] + gArray.Military.Xe[0]*3 < GeneralThaoPhat.SoLuongQuanMinToGo) canrun = false;

					if (GeneralThaoPhat.TuUpSiKhi)
					{
						SetText("Up sỹ khí" + GeneralThaoPhat.GeneralName + "....");
						GeneralThaoPhat.Military.SyKhi = gArray.Military.SyKhi;
						if (!UpSyKhi(GeneralThaoPhat)) canrun = false;
					}

				}

						
				SetText("Điều đi thảo phạt ....");
				idnhiemvu = GeneralThaoPhat.NhiemVuThaoPhatID;
				for (int i = TuongDiThaoPhat.Count; i < 5; i++)
				{
					g[i] = 0;

				}

				if (canrun)
				{
					result = Command.OPT.DanhSonTac(idnhiemvu, g[0], g[1], g[2], g[3], g[4], cookies);
					if (result != null && result["ret"].ToString() == "0")
					{
						//ok, da di thao phat
						result = Command.City.GetCityTask(cookies);
						if (result != null)
						{
							ArrayList task = (ArrayList)result["task"];
							int status = int.Parse(task[2].ToString());
							int time = int.Parse(task[3].ToString());

							if (status != 0)			// Đang di hoặc đang về thao phat
							{
								//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien);
								//LVClient.LVThread.AUTOFIGHTING.startBattle(Batleid, time, SoLuongTuongDanh1Dich, TimeDoiTranHinh, PhuongThucTanCong, GeneralThaoPhat.phuongthucchonmuctieu);
								LVClient.LVThread.AUTOFIGHTING.startBattle(Batleid, time, SoLuongTuongDanh1Dich, TuongDiThaoPhat);
								return;
							}
						}
					}
				}
			}
			catch (Exception ex)
			{
			}
			finally
			{
				Message.ForeColor = System.Drawing.Color.Blue;
			}
		}


		/*private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				LVClient.Command.CityObj.MilitaryGeneral geninfo;
				//bool skok = true;
				//bool luongquanok = false;
				string cookies;
				System.Collections.Hashtable result = null;
				//int sk =100;
				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					Message.ForeColor = System.Drawing.Color.Red;
					SetText("Đang chạy (0%)");
					cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id);
					LVClient.Command.City.SwitchCitySlow(Id);

					result = Command.City.GetCityTask(cookies);
					if (result != null)
					{
						ArrayList task = (ArrayList)result["task"];
						int status = int.Parse(task[2].ToString());
						int time = int.Parse(task[3].ToString());


						if (status != 0)			// Đang di hoặc đang về thao phat	 1: dang di, 2: dang danh, 3: đang trở về
						{
							if (status == 2) time = 0;
							if (status == 1 || status == 2)
							{
								//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien );
								LVClient.LVThread.AUTOFIGHTING.startBattle(Batleid, time, SoLuongTuongDanh1Dich, TimeDoiTranHinh, PhuongThucTanCong, GeneralThaoPhat.phuongthucchonmuctieu);
							}
							return;
						}

					}

					//if(LVClient.Command.CityObj.City.Cantp(Id))
					{


						try
						{
							// bo xung them quan
							if (tubienchequan)
							{
								Common.BienChe oneBienche;

								for (int i = 0; i < LVClient.frmmain.ListBienChe.Count; i++)
								{
									oneBienche = (Common.BienChe)LVClient.frmmain.ListBienChe[i];
									if (oneBienche.cityid == Id &&
										(g1 == oneBienche.generalid || g2 == oneBienche.generalid || g3 == oneBienche.generalid ||
											g4 == oneBienche.generalid || g5 == oneBienche.generalid))
									{
										Common.BienCheQuan.BienChe(oneBienche.cityid, oneBienche.generalid, oneBienche.bobinhamount, oneBienche.kybinhamount, oneBienche.cungthuamount, oneBienche.xemount);
									}
								}
							}
						}
						catch (Exception ex) { }


						if (Upsikhi)
						{
							if (Id > 0)
								Command.Build.SelectBuilding(Id, 16, cookies);
							else
								Command.Build.SelectBuilding(Id, 19, cookies);
						}



						//cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id);
						//LVClient.Command.City.SwitchCitySlow(Id);



						gArray = Command.Common.GetGeneralInforInLuyenBinh(Id);

						bool canrun = true;

						if (gArray != null)
						{
							if (g1 > 0)
								if (!CheckAnUpsiKhi(Id, g1)) canrun = false;

							if (g2 > 0)
								if (!CheckAnUpsiKhi(Id, g2)) canrun = false;

							if (g3 > 0)
								if (!CheckAnUpsiKhi(Id, g3)) canrun = false;

							if (g4 > 0)
								if (!CheckAnUpsiKhi(Id, g4)) canrun = false;

							if (g5 > 0)
								if (!CheckAnUpsiKhi(Id, g5)) canrun = false;
							
							SetText("Đang chạy 50%");



							if (canrun)
							{
								result = Command.OPT.DanhSonTac(idnhiemvu, g1, g2, g3, g4, g5, cookies);
								if (result != null && result["ret"].ToString() == "0")
								{
									//ok, da di thao phat
									result = Command.City.GetCityTask(cookies);
									if (result != null)
									{
										ArrayList task = (ArrayList)result["task"];
										int status = int.Parse(task[2].ToString());
										int time = int.Parse(task[3].ToString());

										if (status != 0)			// Đang di hoặc đang về thao phat
										{
											//LVClient.LVThread.AUTOFIGHTING.startBattle(0, time, 1, 250, Common.WarFunc.PHUONGTHUCTANCONG.HoaTien);
											LVClient.LVThread.AUTOFIGHTING.startBattle(Batleid, time, SoLuongTuongDanh1Dich, TimeDoiTranHinh, PhuongThucTanCong, GeneralThaoPhat.phuongthucchonmuctieu);

											return;
										}
									}
								}
							}


						}
					}
				}
				catch (Exception ex)
				{
				}
				finally
				{
					Message.ForeColor = System.Drawing.Color.Blue;
				}
			} // end lock



		}

		*/
		
		public void run() 
		{
            IsRun = true;
			
			while (true) 
			{
				
                SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));

				threadID = "THAOPHAT_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID , mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
                SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
                Thread.Sleep(Sleep);	 				
            } //end while
			SetText("Dừng bởi lý do nào đó không biết");
        }

		private bool UpSyKhi(Common.GeneralThaoPhat gen)
		{
			bool ret = true;
			if (gen.Military.SyKhi < gen.SiKhiMinToGo) ret = false;

			if (gen.TuUpSiKhi && gen.Military.SyKhi < 100)
				Command.OPT.UpSiKhi(gen.CityID, gen.GeneralId);

			return ret;
		}

		private bool CheckQuanSo(Common.GeneralThaoPhat gen)
		{
			bool ret = true;
			if (gen.Military.Bobinh[0] + gen.Military.KyBinh[0] + gen.Military.CungThu[0] + gen.Military.Xe[0]*3 < gen.SoLuongQuanMinToGo) ret = false;
			return ret;

		}

		/*private bool CheckAnUpsiKhi(int cityid, int genid, int sikhimin)
		{
			try
			{
				bool ret = true;
				gobj = null;
				for (int i = 0; i < gArray.Length; i++)
				{
					if (gArray[i].GeneralId == genid)
					{
						gobj = gArray[i];
						break;
					}
				}

				if (gobj == null)
				{
					ret = false;
				}
				else
				{
					// kiem tra si khi
					// lay si khi
					//sk = Command.Common.GetGeneralSyKhiInLuyenBinh(Id, g1);

					if (gobj.Military.SyKhi < sikhimin) ret = false;


					if (ret)
					{
						// kiem tra so luong quan
						if (gobj.Military.Bobinh[0] + gobj.Military.KyBinh[0] + gobj.Military.CungThu[0] + gobj.Military.Xe[0] < soluongquanmin) ret = false;
					}
				}
				// luyen si khi
				if (Upsikhi && gobj != null && gobj.Military.SyKhi < 100)
					Command.OPT.UpSiKhi(cityid, genid);

				return ret;
			}
			catch (Exception ex)
			{
				return false;
			}

		}
		 */
		public void Auto()
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true; 
				InThread.Start();
			}
		}
        public void Stop() 
		{
            if (IsRun) 
			{
                InThread.Abort();
                InThread.Join();
				Common.ThreadManager.RemoveThread(threadID);
                Message.ForeColor = System.Drawing.Color.Blue ; Message.ForeColor = System.Drawing.Color.Blue ; Message.Text = "Đã dừng bởi người sử dụng";
                IsRun = false;
            }
        }
        private void SetText(String str, System.Drawing.Color color) 
		{
            if (this.Message.InvokeRequired) 
			{
                SetTextCallback d = new SetTextCallback(SetText);
                this.Message.Invoke(d, new object[] { str });
            } 
			else 
			{
				this.Message.ForeColor = color;
                this.Message.Text = str;
            }
        }

		private void SetText(String str)
		{
			if (this.Message.InvokeRequired)
			{
				SetTextCallback d = new SetTextCallback(SetText);
				this.Message.Invoke(d, new object[] { str });
			}
			else
			{					
				this.Message.Text = str;
			}
		}
		
    }
}


