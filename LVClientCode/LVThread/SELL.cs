using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;
using System.Data;

namespace LVClient.LVThread 
{
    public class SELL 
	{
        delegate void SetTextCallback(string text);
        public Thread InThread; public string threadID;
        public bool IsRun = false;

      /*
		int COUNTFOOD;
        int PRICEFOOD;
        int SAFEFOOD;
        int COUNTWOOD;
        int PRICEWOOD;
        int SAFEWOOD;
        int COUNTSTONE;
        int PRICESTONE;
        int SAFESTONE;
        int COUNTIRON;
        int PRICEIRON;
        int SAFEIRON;
        public string[] Cookies;
        public string[] City;
        public int[] Id;
	   */ 
        public int Sleep = 60000;
        public Label Message;
		public int mainProcessResult = 0;

		Command.CommonObj.BanTaiNguyenObj banobj;

        public SELL(Label lbl) 
		{
            Message = lbl;
        }

        /*public void GetParameter_
		(
            int COUNTFOOD, int PRICEFOOD, int SAFEFOOD,
            int COUNTWOOD, int PRICEWOOD, int SAFEWOOD,
            int COUNTSTONE, int PRICESTONE, int SAFESTONE,
            int COUNTIRON, int PRICEIRON, int SAFEIRON, 
            DataGridView dtaSELL, int sleep) 
		{
            if (IsRun == false) 
			{
                this.COUNTFOOD = COUNTFOOD;
                this.COUNTWOOD = COUNTWOOD;
                this.COUNTSTONE = COUNTSTONE;
                this.COUNTIRON = COUNTIRON;

                this.PRICEFOOD = PRICEFOOD;
                this.PRICEWOOD = PRICEWOOD;
                this.PRICESTONE = PRICESTONE;
                this.PRICEIRON = PRICEIRON;

                this.SAFEFOOD = SAFEFOOD;
                this.SAFEWOOD = SAFEWOOD;
                this.SAFESTONE = SAFESTONE;
                this.SAFEIRON = SAFEIRON;

                Cookies = new string[500];
                Id = new int[500];
                this.Sleep = sleep;

                //Xay dung cookies
                int citycount = 0;
                for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++) 
				{
                    if (LVClient.Command.CityObj.City.AllCity[i].id > 0) 
					{
                        Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(LVClient.Command.CityObj.City.AllCity[i].id);
                        Id[citycount] = LVClient.Command.CityObj.City.AllCity[i].id;
                        citycount++;
                    }
                }
                //Nap data
                City = new String[citycount];
                DataTable temp = (DataTable)dtaSELL.DataSource;
                for (int i = 0; i < temp.Rows.Count; i++) {
                    City[i] = ((bool)temp.Rows[i]["SELL_LUA"]).ToString() + "." + ((bool)temp.Rows[i]["SELL_GO"]).ToString() + "." + ((bool)temp.Rows[i]["SELL_DA"]).ToString() + "." + ((bool)temp.Rows[i]["SELL_SAT"]).ToString();
                }
            }
        }
		*/

		public void GetParameter(Command.CommonObj.BanTaiNguyenObj banTaiNguyenObj, int sleep)
		{
			if (IsRun == false)
			{
				this.Sleep = sleep;
				this.banobj = banTaiNguyenObj;
			}
		}

		private int GetPrice(Command.CommonObj.BanTaiNguyenObj.commonInfo resObj, string cookies)
		{
			try
			{
				int price = -1;

				if (resObj.LoaiBan == Command.CommonObj.BanTaiNguyenObj.LOAIBAN.THEOGIACODINH)
				{
					price = (int)Math.Round(resObj.GiaTri);
				}
				else
				{
					if (resObj.LoaiBan == Command.CommonObj.BanTaiNguyenObj.LOAIBAN.THEOGIATRUNGBINH)
					{
						// lay gia trung binh
						price = (int.Parse(Command.OPT.AvgPrice(resObj.ResType).ToString()));
					}
					else	// Ban theo gia thap nhat
					{	// laays bang gia  hien thoi

						price = Command.OPT.GetMinPriceResource(resObj.ResType, cookies);
						if (price ==-1)
							price = (int)((int.Parse(Command.OPT.AvgPrice(resObj.ResType).ToString())) * 1.19);	 					
					}


					if (resObj.CongThucNhan)
						price = (int)Math.Round(price * resObj.GiaTri);
					else
						price = (int)Math.Round(price + resObj.GiaTri);
				} 

				return price;
			}
			catch (Exception ex)
			{
				return -1;
			}

		}
		
		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				string cookies;
				int cityid;
				ArrayList res = new ArrayList();
				int gialua = 0;
				int giago = 0;
				int giasat = 0;
				int giada = 0;

				int soluongban = 0;			// tinh theo tan
				int soluongantoan = 0;		// tinh theo tan

				Hashtable resourse;
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy.... ");
					//-----------------------------------------------------------------------
					if (banobj.CityInfo.Length == 0) return;

					cityid = banobj.CityInfo[0].CityId;
					cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

					gialua = GetPrice(banobj.LUA, cookies);
					giago = GetPrice(banobj.GO, cookies);
					giasat = GetPrice(banobj.SAT, cookies);
					giada =  GetPrice(banobj.DA, cookies);

					Hashtable result =null;
					for (int i = 0; i < banobj.CityInfo.Length; i++)
					{
						try
						{
							SetText("Đang bán ở thành " + banobj.CityInfo[i].CityName + " (" + i + "/" + banobj.CityInfo.Length + ")");
							cityid = banobj.CityInfo[i].CityId;

							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);
							LVClient.Command.City.SwitchCitySlow(cityid);

							//for debug
							//LVClient.Command.CityObj.City city = Command.City.GetCityByID(cityid);
#if (DEBUG)
                            if (Command.Build.SelectBuilding(cityid, 11, cookies) || Command.Build.SelectBuilding(cityid, 64, cookies))
#else
                            if (Command.Build.SelectBuilding(cityid, 11, cookies) )
#endif
                            {
								resourse = Command.City.GetResource(cookies);

								if (resourse == null) continue;

								//string[] info = City[i].Split(new char[] { '.' });
								long currentStoreLua = int.Parse((((ArrayList)resourse["food"])[0]).ToString());
								long currentStoreGo = int.Parse((((ArrayList)resourse["wood"])[0]).ToString());
								long currentStoreDa = int.Parse((((ArrayList)resourse["stone"])[0]).ToString());
								long currentStoreSat = int.Parse((((ArrayList)resourse["iron"])[0]).ToString());
								long maxstore = int.Parse(resourse["max_storage"].ToString());		// dung luong kho
								// Ban lua
								if (banobj.CityInfo[i].BanLua)
								{
									//SetText("Đang bán " + LVClient.Command.City.GetCityByID(cityid).name + "...");

									res = (ArrayList)resourse["food"];

									if (banobj.LUA.BanCoDinh)
									{
										soluongban = banobj.LUA.SoLuongBan;
										soluongantoan = banobj.LUA.SoLuongAnToan;
									}
									else         // tinhs theo %
									{
										soluongban =  (int)(Math.Floor ( (double) (((banobj.LUA.SoLuongBan * maxstore / 1000)/100 ) )));
										soluongantoan = (int)(Math.Floor((double)((((banobj.LUA.SoLuongAnToan * maxstore / 1000) / 100)))));
									}

									//if (int.Parse(res[0].ToString()) >= (banobj.LUA.SoLuongAnToan * 1000) + banobj.LUA.SoLuongBan * 1000)
									if (int.Parse(res[0].ToString()) >= (soluongantoan + soluongban) * 1000)
									{
										//result = Command.OPT.SellFood(banobj.LUA.SoLuongBan, gialua, 1, cookies);
										result = Command.OPT.SellFood(soluongban, gialua, 1, cookies);
										if (result["ret"].ToString() == "249")		// day list
										{
											if (changePrice(cookies)) return;
										}
									}
								}

								if (banobj.CityInfo[i].BanGo)
								{
									res = (ArrayList)resourse["wood"];
									if (banobj.GO.BanCoDinh)
									{
										soluongban = banobj.GO.SoLuongBan;
										soluongantoan = banobj.GO.SoLuongAnToan;
									}
									else         // tinhs theo %
									{
										soluongban = (int)(Math.Floor((double)(((banobj.GO.SoLuongBan * maxstore / 1000) / 100))));
										soluongantoan = (int)(Math.Floor((double)((((banobj.GO.SoLuongAnToan * maxstore / 1000) / 100)))));
									}



									//if (int.Parse(res[0].ToString()) >= (banobj.GO.SoLuongAnToan * 1000) + banobj.GO.SoLuongBan * 1000)
									if (int.Parse(res[0].ToString()) >= (soluongantoan + soluongban) * 1000)
									{
										//result = Command.OPT.SellFood(banobj.GO.SoLuongBan, giago, 2, cookies);

										result = Command.OPT.SellFood(soluongban, giago, 2, cookies);
										if (result["ret"].ToString() == "249")		// day list
										{
											if (changePrice(cookies)) return;
										}
										if (result["ret"].ToString() == "0")		// ok
										{

										}
									}
								}
								if (banobj.CityInfo[i].BanDa)
								{

									res = (ArrayList)resourse["stone"];

									if (banobj.DA.BanCoDinh)
									{
										soluongban = banobj.DA.SoLuongBan;
										soluongantoan = banobj.DA.SoLuongAnToan;
									}
									else         // tinhs theo %
									{
										soluongban = (int)(Math.Floor((double)(((banobj.DA.SoLuongBan * maxstore / 1000) / 100))));
										soluongantoan = (int)(Math.Floor((double)((((banobj.DA.SoLuongAnToan * maxstore / 1000) / 100)))));
									}

									//if (int.Parse(res[0].ToString()) >= (banobj.DA.SoLuongAnToan * 1000) + banobj.DA.SoLuongBan * 1000)
									if (int.Parse(res[0].ToString()) >= (soluongantoan + soluongban) * 1000)
									{
										//result = Command.OPT.SellFood(banobj.DA.SoLuongBan, giada, 3, cookies);
										result = Command.OPT.SellFood(soluongban, giada, 3, cookies);
										if (result["ret"].ToString() == "249")		// day list
										{
											if (changePrice(cookies)) return;
										}
									}
								}


								if (banobj.CityInfo[i].BanSat)
								{
									res = (ArrayList)resourse["iron"];
									if (banobj.SAT.BanCoDinh)
									{
										soluongban = banobj.SAT.SoLuongBan;
										soluongantoan = banobj.SAT.SoLuongAnToan;
									}
									else         // tinhs theo %
									{
										soluongban = (int)(Math.Floor((double)(((banobj.SAT.SoLuongBan * maxstore / 1000) / 100))));
										soluongantoan = (int)(Math.Floor((double)((((banobj.SAT.SoLuongAnToan * maxstore / 1000) / 100)))));
									}
									
									//if (int.Parse(res[0].ToString()) >= (banobj.SAT.SoLuongAnToan * 1000) + banobj.SAT.SoLuongBan * 1000)
									if (int.Parse(res[0].ToString()) >= (soluongantoan + soluongban) * 1000)
									{
										//result = Command.OPT.SellFood(banobj.SAT.SoLuongBan, giasat, 4, cookies);
										result = Command.OPT.SellFood(soluongban, giasat, 4, cookies);
										if (result["ret"].ToString() == "249")		// day list
										{
											if (changePrice(cookies)) return;
										}
									}
								}


								if (result == null)  // fail or không bán cái gì
								{
								}
								else
								{
									mainProcessResult = int.Parse(result["ret"].ToString());
									if (mainProcessResult > 1000000) // bi lock
									{
										return;
									}
								}
							}


						}
						catch (Exception ex1)
						{
							//MessageBox.Show(ex1.ToString());
							//SetText("Đang bán ở thành " + banobj.CityInfo[i].CityName + " (" + i + "/" + banobj.CityInfo.Length + ")");
						}
					}
				}
				catch (Exception ex)
				{
					//MessageBox.Show(ex.ToString());
				}
				//}
			}
		}

		// thay doi gia thap hon gia thap nhat de ban duoc trong truong hop tro day tai nguyen
		private bool changePrice(string cookies)
		{
			const int MaxItemChange = 10;
			const int GiaThapMin = 5;
			try
			{
				if (!banobj.SalesOff) return true;


				int minlua = Command.OPT.GetMinPriceResource(LVClient.LVThread.BUYRES.RESOURCETYPE.LUA, cookies);
				int mingo = Command.OPT.GetMinPriceResource(LVClient.LVThread.BUYRES.RESOURCETYPE.GO, cookies);
				int minda = Command.OPT.GetMinPriceResource(LVClient.LVThread.BUYRES.RESOURCETYPE.DA, cookies);
				int minsat = Command.OPT.GetMinPriceResource(LVClient.LVThread.BUYRES.RESOURCETYPE.SAT, cookies);

				Hashtable listdangban = Command.Common.Execute(38, "stab=2", true);
				if (listdangban == null) return false;
				ArrayList infos = (ArrayList)listdangban["infos"];
				Hashtable infoitem;

				object objtemp;
				int count1, count2;

				/*
				{"infos":
				 * [{"seqno":"2504711","city":"20118","count":"3404","price":"818","type":"4","time":"10/1/2009 10:55:07 PM"},
				 * { "seqno":"2504710","city":"10718","count":"3430","price":"584","type":"2","time":"10/1/2009 10:54:49 PM"},
				 * { "seqno":"2496737","city":"101502","count":"3430","price":"211","type":"1","time":"10/1/2009 5:42:51 AM"},{"seqno":"2496732","city":"94703","count":"3430","price":"211","type":"1","time":"10/1/2009 5:34:55 AM"},{"seqno":"2496522","city":"20118","count":"3430","price":"211","type":"1","time":"10/1/2009 3:12:38 AM"},{"seqno":"2496521","city":"20118","count":"3430","price":"211","type":"1","time":"10/1/2009 3:12:37 AM"},{"seqno":"2496520","city":"20118","count":"3430","price":"211","type":"1","time":"10/1/2009 3:12:35 AM"},{"seqno":"2496443","city":"22881","count":"3430","price":"211","type":"1","time":"10/1/2009 2:15:38 AM"},{"seqno":"2496407","city":"28200","count":"3430","price":"211","type":"1","time":"10/1/2009 1:55:56 AM"},{"seqno":"2496307","city":"46999","count":"3430","price":"211","type":"1","time":"10/1/2009 1:30:02 AM"},{"seqno":"2496035","city":"93938","count":"3430","price":"211","type":"1","time":"10/1/2009 12:34:34 AM"},{"seqno":"2494211","city":"101502","count":"3430","price":"218","type":"1","time":"9/30/2009 9:10:41 PM"},{"seqno":"2494029","city":"28200","count":"3430","price":"218","type":"1","time":"9/30/2009 8:46:47 PM"},{"seqno":"2493992","city":"22881","count":"3430","price":"218","type":"1","time":"9/30/2009 8:37:40 PM"},{"seqno":"2493982","city":"13835","count":"3430","price":"218","type":"1","time":"9/30/2009 8:37:03 PM"},{"seqno":"2349485","city":"22881","count":"3430","price":"787","type":"2","time":"9/16/2009 4:11:56 PM"},{"seqno":"2349484","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 4:11:30 PM"},{"seqno":"2344690","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 4:35:17 AM"},{"seqno":"2344148","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 1:58:16 AM"},{"seqno":"2344121","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 1:54:20 AM"},{"seqno":"2344105","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 1:53:27 AM"},{"seqno":"2344081","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 1:46:49 AM"},{"seqno":"2344062","city":"10718","count":"3430","price":"787","type":"2","time":"9/16/2009 1:40:25 AM"},{"seqno":"2341646","city":"10718","count":"3430","price":"745","type":"2","time":"9/15/2009 7:41:41 PM"},{"seqno":"2220140","city":"39557","count":"3430","price":"1020","type":"2","time":"9/2/2009 5:09:33 PM"}]}
			*/


				// Sắp xếp theo thứ tự tăng dần của số lượng, hạ giá thằng nào có số lượng ít nhất, 
				//nếu cùng số lượng thì hạ giá thằng bán trước (seqno nhỏ hơn)
				for (int i=0; i < infos.Count; i++)
					for (int j = i + 1; j < infos.Count; j++)
					{
						count1 = int.Parse(((Hashtable)infos[i])["count"].ToString());
						count2 = int.Parse(((Hashtable)infos[j])["count"].ToString());
						
						
						if (count1 > count2 || 
							(
							count1 == count2 &&
								long.Parse(((Hashtable)infos[i])["seqno"].ToString()) > long.Parse(((Hashtable)infos[j])["seqno"].ToString())
							)
							
							)
						
						{
							objtemp = infos[i];
							infos[i] = infos[j];
							infos[j] = objtemp;

						}
 
					}

			
				int seqno;
				int type;
				int price = -1;
				Hashtable ret;
				for (int i = 0; i < MaxItemChange; i++)
				{
					infoitem = (Hashtable)infos[i];
					seqno = int.Parse(infoitem["seqno"].ToString());
					type = int.Parse(infoitem["type"].ToString());
					// change price
					switch (type)
					{
						case  LVClient.LVThread.BUYRES.RESOURCETYPE.LUA:
							price = minlua - GiaThapMin;
							break;
						
						case LVClient.LVThread.BUYRES.RESOURCETYPE.GO:
							price = mingo - GiaThapMin;
							break;
						case LVClient.LVThread.BUYRES.RESOURCETYPE.DA:
							price = minda - GiaThapMin;
							break;
						case LVClient.LVThread.BUYRES.RESOURCETYPE.SAT:
							price = minsat - GiaThapMin;
							break;
					}

					if (price < 0) continue;

					ret = Command.OPT.Execute(68, "price=" + price + "&seqno=" + seqno + "&tid=0", true);

				}

				return true;
			}
			catch (Exception ex)
			{
				return false;
			}
		}


		public void run()
		{
			IsRun = true;
			
			while (true)
			{
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "SELL_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID , mainprocess);
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
        



        /*public void run() 
		{
            IsRun = true;
            while (true) 
			{
                SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
                lock (LVClient.Web.LVWeb.islock) {
                    //lock (LVClient.Web.LVWeb.ispause) {
                        try {
                            SetText("Đang chạy.... ");
                            for (int i = 0; i < City.Length; i++) 
							{								
                                try 
								{
                                    Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
                                    LVClient.Command.City.SwitchCitySlow(Id[i]);

									//for debug
									//LVClient.Command.CityObj.City city = Command.City.GetCityByID(Id[i]);

                                    if (Command.Build.SelectBuilding(Id[i], 11, Cookies[i])) 
									{
                                        Hashtable resourse = Command.City.GetResource(Cookies[i]);

                                        string[] info = City[i].Split(new char[] { '.' });

                                        if (info[0].ToLower() == "true") 
										{
											SetText("Đang bán " + LVClient.Command.City.GetCityByID(Id[i]).name + "...");

                                            ArrayList res = new ArrayList();
                                            res = (ArrayList)resourse["food"];
                                            if (int.Parse(res[0].ToString()) > (SAFEFOOD * 1000) + COUNTFOOD * 1000) 
											{
                                                Command.OPT.SellFood(COUNTFOOD, PRICEFOOD, 1, Cookies[i]);
                                                //LVClient.Web.LVWeb.idimage = -1;
                                            }
                                        }
                                        if (info[1].ToLower() == "true") {
                                            ArrayList res = new ArrayList();
                                            res = (ArrayList)resourse["wood"];
                                            if (int.Parse(res[0].ToString()) > (SAFEWOOD * 1000) + COUNTWOOD * 1000) {
                                                Command.OPT.SellFood(COUNTWOOD, PRICEWOOD, 2, Cookies[i]);
                                            }
                                        }
                                        if (info[2].ToLower() == "true") {
                                            ArrayList res = new ArrayList();
                                            res = (ArrayList)resourse["stone"];
                                            if (int.Parse(res[0].ToString()) > (SAFESTONE * 1000) + COUNTSTONE * 1000) {
                                                Command.OPT.SellFood(COUNTSTONE, PRICESTONE, 3, Cookies[i]);
                                            }
                                        }
                                        if (info[3].ToLower() == "true") {
                                            ArrayList res = new ArrayList();
                                            res = (ArrayList)resourse["iron"];
                                            if (int.Parse(res[0].ToString()) > (SAFEIRON * 1000) + COUNTIRON * 1000) {
                                                Command.OPT.SellFood(COUNTIRON, PRICEIRON, 4, Cookies[i]);
                                            }
                                        }
                                    }
                                } catch (Exception ex1) 
								{
                                    //MessageBox.Show(ex1.ToString());
                                }
                            }
                        } catch (Exception ex) {
                            //MessageBox.Show(ex.ToString());
                        }
                    //}
                }
                SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
                Thread.Sleep(Sleep);
            }
        }
        */


		public void Auto()
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true;  InThread.Start();
			}
		}
        public void Stop() {
            if (IsRun) {
                InThread.Abort();
                InThread.Join();
				Common.ThreadManager.RemoveThread(threadID);
               
				Message.ForeColor = System.Drawing.Color.Blue ; 
				Message.Text = "Đã dừng bởi người sử dụng";
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
