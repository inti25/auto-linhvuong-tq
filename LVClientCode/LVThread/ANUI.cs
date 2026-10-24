using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

namespace LVClient.LVThread 
{
    public class ANUI {
        delegate void SetTextCallback(string text);
        public Thread InThread;
		public string threadID;  
        public bool IsRun = false;
        //public string[] Cookies;
        //public string[] City;
        //public int[] Id;
		public int[] Cityid;
        //public int citycount;
        public int Sleep = 60000;
		public bool isTuMuaLua;
		public long VangAnToan;
        public Label Message;
		public int mainProcessResult = 0;
		

        public ANUI(Label lbl) {
            Message = lbl;
        }
        
		/*public void GetParameter1(DataGridView dtaAnUi, int sleep) {
			try
			{
				if (IsRun == false)
				{

					Cookies = new string[500];
					Id = new int[500];
					this.Sleep = sleep;

					//Xay dung cookies
					citycount = 0;
					for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
					{
						if (LVClient.Command.CityObj.City.AllCity[i].id > 0)
						{
							Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(LVClient.Command.CityObj.City.AllCity[i].id);
							Id[citycount] = LVClient.Command.CityObj.City.AllCity[i].id;
							citycount++;
						}
					}

					City = new string[citycount];
					DataTable temp = (DataTable)dtaAnUi.DataSource;
					for (int i = 0; i < temp.Rows.Count; i++)
					{
						City[i] = temp.Rows[i]["ADD_NK"].ToString();
					}
				}
			}
			catch (Exception ex)
			{
				LVClient.frmmain.LVFRMMAIN.lblANUIMESSAGE.Text = "Chưa chọn đúng tham số";
				LVClient.frmmain.LVFRMMAIN.chkAutoUpDanSo.Checked = false;
			}
        }
		 * */

		public void GetParameter(ArrayList dtaAnUi, bool tumualua, long vangantoan, int sleep)
		{
			try
			{
				if (IsRun == false)
				{

					//Cookies = new string[500];
					//Id = new int[500];
					this.Sleep = sleep;
					this.isTuMuaLua = tumualua;
					this.VangAnToan = vangantoan;
					
					Cityid = new int[dtaAnUi.Count];
					for (int i = 0; i < dtaAnUi.Count; i++)
					{
						Cityid[i] = int.Parse( dtaAnUi[i].ToString());
					}
				}
			}
			catch (Exception ex)
			{
				LVClient.frmmain.LVFRMMAIN.lblANUIMESSAGE.Text = "Chưa chọn đúng tham số";
				LVClient.frmmain.LVFRMMAIN.chkAutoUpDanSo.Checked = false;
			}
		}

		private void mainprocess()
		{
			
			Hashtable citysimple;
			ArrayList aino;
			ArrayList arTemp;
			string cookies;
			Hashtable result = null;
			int repeat = 0;
			long safegold = VangAnToan;
			
			//lock (LVClient.Web.LVWeb.islock)
			{
				
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");
					Command.CityObj.City city;

					for (int i = 0; i < Cityid.Length; i++)
					{	  			

						try
						{
							city = Command.City.GetCityByID(Cityid[i]);
							SetText("Đang an ủi thành " + city.name + "(" + i + "/" + Cityid.Length + ")");

							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Cityid[i]);
							LVClient.Command.City.SwitchCitySlow(Cityid[i]);
							citysimple = Command.City.GetCitySimpleInfo(cookies); 						

							aino = (ArrayList)citysimple["morale"];
							result = null;
							if (Command.Build.SelectBuilding(Cityid[i], 1, 8, 0, cookies))
							{
								repeat = 0;
								while (true && repeat < 3)
								{
									if (int.Parse(aino[2].ToString()) > 0)	  // dan no
									{
										result = Command.OPT.QuanPhuAnUi(3, cookies);	 // tế thiên
									}
									else
									{
										result = Command.OPT.QuanPhuAnUi(4, cookies);		// an ủi
									}

									if (result == null)
									{
									}
									else
									{
									
										mainProcessResult = int.Parse(result["ret"].ToString());
										if (mainProcessResult == 0)   // thanh cong
										{
										}
										if (mainProcessResult == 55)   // an ủi nhiều lần
										{
										}

										if (mainProcessResult == 32)	 // thieu lua
										{
											if (isTuMuaLua)
											{
												repeat++;
												arTemp = (ArrayList)citysimple["money"];
												long gold = int.Parse(arTemp[0].ToString());					// vang hien co
												if (gold <= safegold) break;				// không đủ vàng, đành thôi vậy
												gold = gold - safegold;
												arTemp = (ArrayList)citysimple["population"];
												int population = int.Parse(arTemp[0].ToString());
												int needfood = population * 10;
												Hashtable ResHave = Command.City.GetCurentResourceInCity(cookies);
												int maxkho = int.Parse(ResHave["MAXKHO"].ToString());
												int haveValue = int.Parse(ResHave["LUA"].ToString());

												if (needfood > maxkho) break;			// không đủ kho
												needfood = needfood - haveValue;
												if (needfood <= 0) continue;			// vẫn còn đủ lúa

												Command.OPT.BuyRes(Common.Constant.RESOURCETYPE.LUA, (double)needfood, ref gold, cookies);
												continue;
											}
										}

									
										if (mainProcessResult > 1000000) // bi lock
										{
											return;
										}

									}
									break;
								}	  // end while (true)
							}	 //end if (Command.Build.SelectBuilding(Cityid[i], 1, 8, 0, cookies))
						}
						catch (Exception ex)
						{
						}

					}
				}
				catch (Exception ex)
				{
				}
				//}
			}
		}
		
		
		public void run()
		{
			IsRun = true;
			
			while (true)
			{
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));

				threadID = "ANUI_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				if (mainProcessResult > 1000000)
				{
					SetText("Bị khóa đến " + DateTime.Now.AddSeconds(mainProcessResult - 1000000).ToString("HH:mm:ss")
						+ ". Đang ngủ " + Sleep / (1000 * 60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				} 
				Thread.Sleep(Sleep);
			}
		}

		/*public void run1() {
            IsRun = true;
            while (true) {
                SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				Hashtable citysimple;
				ArrayList aino;
				lock (LVClient.Web.LVWeb.islock) {
                    //lock (LVClient.Web.LVWeb.ispause) {
                        try {
                            SetText("Đang chạy (0%)");
                            for (int i = 0; i < City.Length; i++) 
							{
                                SetText("Đang chạy (" + (i) * 100 / City.Length + "%)");
                                if (City[i].ToLower() == "true") 
								{
                                    Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
                                    LVClient.Command.City.SwitchCitySlow(Id[i]);
                                    citysimple = Command.City.GetCitySimpleInfo(Cookies[i]);
                                    aino = (ArrayList)citysimple["morale"];
                                    if (Command.Build.SelectBuilding(Id[i], 1, 8, 0, Cookies[i])) 
									{
                                        if (int.Parse(aino[2].ToString()) > 0) {
                                            Command.OPT.QuanPhuAnUi(3, Cookies[i]);
                                        } else {
                                            Command.OPT.QuanPhuAnUi(4, Cookies[i]);
                                        }
                                    }
                                }
                            }
                        } catch (Exception ex) {
                        }
                    //}
                }
                SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
                Thread.Sleep(Sleep);
            }
        } */
        public void Auto() 
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true;  InThread.Start();
			}
        }
        public void Stop() 
		{
            if (IsRun) 
			{

                InThread.Abort();
                InThread.Join();
				Common.ThreadManager.s_alRegister.Remove(threadID);

                Message.ForeColor = System.Drawing.Color.Blue ; Message.ForeColor = System.Drawing.Color.Blue ; Message.Text = "Đã dừng bởi người sử dụng";
                IsRun = false;
            }
        }
        private void SetText(String str) {
            if (this.Message.InvokeRequired) {
                SetTextCallback d = new SetTextCallback(SetText);
                this.Message.Invoke(d, new object[] { str });
            } else {
                this.Message.Text = str;
            }
        }
    }
}
