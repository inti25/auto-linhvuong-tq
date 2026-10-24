using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

namespace LVClient.LVThread {
    public class BUYRES {
        delegate void SetTextCallback(string text);
        public Thread InThread; public string threadID;
        public bool IsRun = false;
        public long SAFEGOLD;
        public string[] Cookies;
        public string[] City;
        public int citycount;
        public int[] Id;
        public int Sleep = 60000;
        public Label Message;

		Command.CommonObj.MuaTaiNguyenObj muaObj;

		public BUYRES(Label lbl) 
		{
            Message = lbl;
        }
        /*public void GetParameter(int SAFEGOLD,DataGridView dtaSELL, int sleep) 
		{
            if (IsRun == false) {
                this.SAFEGOLD = SAFEGOLD;

                Cookies = new string[500];
                City = new string[500];
                Id = new int[500];
                this.Sleep = sleep;

                //Xay dung cookies
                citycount = 0;

                //Nap data
                DataTable temp = (DataTable)dtaSELL.DataSource;
                for (int i = 0; i < temp.Rows.Count; i++) {
                    City[citycount] = ((bool)temp.Rows[i]["BUY_LUA"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_GO"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_DA"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_SAT"]).ToString();
                    Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(int.Parse(temp.Rows[i]["ID_TT"].ToString()));
                    Id[citycount] = int.Parse(temp.Rows[i]["ID_TT"].ToString());
                    citycount++;
                }
            }
        }
		*/



		public void GetParameter(Command.CommonObj.MuaTaiNguyenObj muaTaiNguyenObj)
		{
			if (IsRun == false)
			{
				this.SAFEGOLD = muaTaiNguyenObj.VangAnToan;
				this.muaObj = muaTaiNguyenObj;

				Cookies = new string[500];
				City = new string[500];
				Id = new int[500];
				this.Sleep = (int) muaTaiNguyenObj.TimeToRunInMinute * 60 * 1000;

				//Xay dung cookies
				citycount = 0;

				//Nap data
				//DataTable temp = (DataTable)dtaSELL.DataSource;
				//for (int i = 0; i < temp.Rows.Count; i++)
				//{
				//	City[citycount] = ((bool)temp.Rows[i]["BUY_LUA"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_GO"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_DA"]).ToString() + "." + ((bool)temp.Rows[i]["BUY_SAT"]).ToString();
				//	Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(int.Parse(temp.Rows[i]["ID_TT"].ToString()));
				//	Id[citycount] = int.Parse(temp.Rows[i]["ID_TT"].ToString());
				//	citycount++;
				//}
			}
		}

		public static class RESOURCETYPE
		{
			public const int LUA = 1;
			public const int GO = 2;
			public const int DA = 3;
			public const int SAT = 4;
		}

	
		/*private void buyresource(int restype, double buyamount, ref long gold, string cookies)
		{
			{
				int repeat = 0;
				Hashtable market =null;
				do
				{
					 market = Command.Common.GetMarketSeller(restype, cookies);
					 repeat++;
				 } while (market == null & repeat < 5);
				ArrayList infos = (ArrayList)market["infos"];
				//int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
				int resbuy = (int)System.Math.Floor((buyamount / 1000));

				Hashtable infoitem;
				if (resbuy > 0)
				{
					//duyet cho den khi het mang
					for (int j = 0; j < infos.Count; j++)
					{
						infoitem = (Hashtable)infos[j];
						int price = int.Parse(infoitem["price"].ToString());
						int count = int.Parse(infoitem["count"].ToString());
						int seller = int.Parse(infoitem["seller"].ToString());
						int seqno = int.Parse(infoitem["seqno"].ToString());

						//neu mua het luon
						if (gold - count * price >= 0)
						{
							if (resbuy - count >= 0)
							{
								Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, cookies);
								resbuy -= count;
								gold -= count * price;
							}
							else
							{
								Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, cookies);
								gold -= resbuy * price;
								resbuy = 0;								
							}
						}
						else if (gold - resbuy * price >= 0)
						{
							if (resbuy - count >= 0)
							{
								Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, cookies);
								resbuy -= count;
								gold -= count * price;
							}
							else
							{
								Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, cookies);
								gold -= resbuy * price;
								resbuy = 0;
							}
							resbuy -= count;
						}
						if (resbuy <= 0) break;
					}
				}
			}
		}
		*/
		private void mainprocess()
		{

			//lock (LVClient.Web.LVWeb.islock)
			{
				string cookies;
				int cityid;

				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					//LVClient.Web.LVWeb.processCheckImage();
					//SetText("Đang chạy (0%)");
					Message.ForeColor = System.Drawing.Color.Red; 

					for (int i = 0; i < muaObj.CityInfo.Length; i++)
					{

						SetText("Đang mua " + muaObj.CityInfo[i].CityName + "(" + i + "/" + muaObj.CityInfo.Length + ")");
						try
						{

							cityid = muaObj.CityInfo[i].CityId;
							LVClient.Command.City.SwitchCitySlow(cityid);
							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

#if (DEBUG)
                            if (Command.Build.SelectBuilding(cityid, 11, cookies) || Command.Build.SelectBuilding(cityid, 64, cookies))  // chợ
#else
                            if (Command.Build.SelectBuilding(cityid, 11, cookies) ) 
#endif
                            {
							
                            Hashtable cityinfo = Command.City.GetCitySimpleInfo(cookies);
                            if (cityinfo == null) continue;
                            
                            ArrayList goldarr = (ArrayList)cityinfo["money"];

							long gold = int.Parse(goldarr[0].ToString());					// vang hien co
							if (gold <= muaObj.VangAnToan) continue;
							gold = gold - muaObj.VangAnToan;

							Hashtable resourse = Command.City.GetResource(cookies);

							long maxstore = int.Parse(resourse["max_storage"].ToString());		// dung luong kho

							long currentStoreLua = int.Parse((((ArrayList)resourse["food"])[0]).ToString());
							long currentStoreGo = int.Parse((((ArrayList)resourse["wood"])[0]).ToString());
							long currentStoreDa = int.Parse((((ArrayList)resourse["stone"])[0]).ToString());
							long currentStoreSat = int.Parse((((ArrayList)resourse["iron"])[0]).ToString());

							double maxstorecanbuy;					// gioi han mua
							if (muaObj.MuaTheoDonViKho)
							{
								maxstorecanbuy = muaObj.GiaTri > maxstore ? maxstore : muaObj.GiaTri;
							}
							else
							{
								maxstorecanbuy = Convert.ToInt64(maxstore * muaObj.GiaTri / 100);
								if (maxstorecanbuy > maxstore) maxstorecanbuy = maxstore;
							}

								//muaObj.CityInfo[i].Vitridangmua = (new Random()).Next(4);
								for (int k = 0; k < 4; k++)
								{
									if (muaObj.CityInfo[i].Vitridangmua > 3) muaObj.CityInfo[i].Vitridangmua = 0;

									switch (muaObj.CityInfo[i].Vitridangmua)
									{
										case 0:		//mua lua											

											// mua lua. chi mua 1/4 luong can thiet moi lan
											if (muaObj.CityInfo[i].MuaLua && gold > 0 && currentStoreLua < maxstorecanbuy)
												Command.OPT.BuyRes(RESOURCETYPE.LUA, (maxstorecanbuy - currentStoreLua) / 1, ref gold, cookies);

											muaObj.CityInfo[i].Vitridangmua += 1;

											break;

										case 1:		//mua go
											

											if (muaObj.CityInfo[i].MuaGo && gold > 0 && currentStoreGo < maxstorecanbuy)
												Command.OPT.BuyRes(RESOURCETYPE.GO, (maxstorecanbuy - currentStoreGo) / 1, ref gold, cookies);

											muaObj.CityInfo[i].Vitridangmua += 1;
											break;

										case 2:		//mua da
											

											if (muaObj.CityInfo[i].MuaDa && gold > 0 && currentStoreDa < maxstorecanbuy)
												Command.OPT.BuyRes(RESOURCETYPE.DA, (maxstorecanbuy - currentStoreDa) / 1, ref gold, cookies);

											muaObj.CityInfo[i].Vitridangmua += 1;
											break;

										case 3:		//mua sat											

											if (muaObj.CityInfo[i].MuaSat && gold > 0 && currentStoreSat < maxstorecanbuy)
												Command.OPT.BuyRes(RESOURCETYPE.SAT, (maxstorecanbuy - currentStoreSat) / 1, ref gold, cookies);

											muaObj.CityInfo[i].Vitridangmua += 1;
											break;
									}
								}  // end for (int k = 0; k < 4; k++)
							}
						}
						catch (Exception ex1)
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
				threadID = "BUYRES_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				Thread.Sleep(Sleep);
			}
		}


		/*public void run() 
		{
			IsRun = true;
			while (true) {
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				lock (LVClient.Web.LVWeb.islock) 
				{
					//lock (LVClient.Web.LVWeb.ispause) {
						try {
							SetText("Đang chạy (0%)");


							for (int i = 0; i < citycount; i++) 
							{

								SetText("Đang chạy (" + (i) * 100 / citycount + "%)");
								try {
									Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
									LVClient.Command.City.SwitchCitySlow(Id[i]);
									Hashtable cityinfo = Command.City.GetCitySimpleInfo(Cookies[i]);
									Hashtable resourse = Command.City.GetResource(Cookies[i]);

									ArrayList goldarr = (ArrayList)cityinfo["money"];

									int gold = int.Parse(goldarr[0].ToString());
									int store = int.Parse(resourse["max_storage"].ToString());

									string[] info = City[i].Split(new char[] { '.' });
									if (Command.Build.SelectBuilding(Id[i], 11, Cookies[i])) {
										//ban lua
										if (info[0].ToLower() == "true") {
											ArrayList res = new ArrayList();
											res = (ArrayList)resourse["food"];
											if (int.Parse(res[0].ToString()) / store < 0.9) {
												Hashtable market = Command.Common.GetMarketSeller(1, Cookies[i]);
												ArrayList infos = (ArrayList)market["infos"];
												int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
												if (resbuy > 0) {
													//duyet cho den khi het mang
													for (int j = 0; j < infos.Count; j++) {
														Hashtable infoitem = (Hashtable)infos[j];
														int price = int.Parse(infoitem["price"].ToString());
														int count = int.Parse(infoitem["count"].ToString());
														int seller = int.Parse(infoitem["seller"].ToString());
														int seqno = int.Parse(infoitem["seqno"].ToString());

														//neu mua het luon
														if (gold - count * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, Cookies[i]);
																resbuy = 0;
															}
														} else if (gold - resbuy * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 1, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 1, count, price, Cookies[i]);
																resbuy = 0;
															}
															resbuy -= count;
														}
														if (resbuy <= 0) break;
													}
												}
											}
										}
										//ban go
										if (info[1].ToLower() == "true") {
											ArrayList res = new ArrayList();
											res = (ArrayList)resourse["wood"];
											if (int.Parse(res[0].ToString()) / store < 0.9) {
												Hashtable market = Command.Common.GetMarketSeller(2, Cookies[i]);
												ArrayList infos = (ArrayList)market["infos"];
												int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
												if (resbuy > 0) {
													//duyet cho den khi het mang
													for (int j = 0; j < infos.Count; j++) {
														Hashtable infoitem = (Hashtable)infos[j];
														int price = int.Parse(infoitem["price"].ToString());
														int count = int.Parse(infoitem["count"].ToString());
														int seller = int.Parse(infoitem["seller"].ToString());
														int seqno = int.Parse(infoitem["seqno"].ToString());

														//neu mua het luon
														if (gold - count * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 2, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 2, count, price, Cookies[i]);
																resbuy = 0;
															}
														} else if (gold - resbuy * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 2, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 2, count, price, Cookies[i]);
																resbuy = 0;
															}
															resbuy -= count;
														}
														if (resbuy <= 0) break;
													}
												}
											}
										}
										//ban da
										if (info[2].ToLower() == "true") {
											ArrayList res = new ArrayList();
											res = (ArrayList)resourse["stone"];
											if (int.Parse(res[0].ToString()) / store < 0.9) {
												Hashtable market = Command.Common.GetMarketSeller(3, Cookies[i]);
												ArrayList infos = (ArrayList)market["infos"];
												int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
												if (resbuy > 0) {
													//duyet cho den khi het mang
													for (int j = 0; j < infos.Count; j++) {
														Hashtable infoitem = (Hashtable)infos[j];
														int price = int.Parse(infoitem["price"].ToString());
														int count = int.Parse(infoitem["count"].ToString());
														int seller = int.Parse(infoitem["seller"].ToString());
														int seqno = int.Parse(infoitem["seqno"].ToString());

														//neu mua het luon
														if (gold - count * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 3, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 3, count, price, Cookies[i]);
																resbuy = 0;
															}
														} else if (gold - resbuy * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 3, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 3, count, price, Cookies[i]);
																resbuy = 0;
															}
															resbuy -= count;
														}
														if (resbuy <= 0) break;
													}
												}
											}
										}
										//ban sat
										if (info[3].ToLower() == "true") {
											ArrayList res = new ArrayList();
											res = (ArrayList)resourse["iron"];
											if (int.Parse(res[0].ToString()) / store < 0.9) {
												Hashtable market = Command.Common.GetMarketSeller(4, Cookies[i]);
												ArrayList infos = (ArrayList)market["infos"];
												int resbuy = (int)System.Math.Floor((double)(90 * store / 100 - int.Parse(res[0].ToString())) / 1000);
												if (resbuy > 0) {
													//duyet cho den khi het mang
													for (int j = 0; j < infos.Count; j++) {
														Hashtable infoitem = (Hashtable)infos[j];
														int price = int.Parse(infoitem["price"].ToString());
														int count = int.Parse(infoitem["count"].ToString());
														int seller = int.Parse(infoitem["seller"].ToString());
														int seqno = int.Parse(infoitem["seqno"].ToString());

														//neu mua het luon
														if (gold - count * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 4, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 4, count, price, Cookies[i]);
																resbuy = 0;
															}
														} else if (gold - resbuy * price > SAFEGOLD) {
															if (resbuy - count >= 0) {
																Command.OPT.BuyRes(count, price, seqno, seller, 4, count, price, Cookies[i]);
																resbuy -= count;
															} else {
																Command.OPT.BuyRes(resbuy, price, seqno, seller, 4, count, price, Cookies[i]);
																resbuy = 0;
															}
															resbuy -= count;
														}
														if (resbuy <= 0) break;
													}
												}
											}
										}
									}
								} 
								catch (Exception ex1) {
                                    
								}
							}
						}
						catch (Exception ex) {
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
            InThread.Abort();
            InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
            Message.ForeColor = System.Drawing.Color.Blue ; Message.Text = "Đã dừng bởi người sử dụng";
            IsRun = false;
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
