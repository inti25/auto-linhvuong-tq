using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread {
    public class  BUILD {
        delegate  void SetTextCallback(string text);

		public Thread InThread; public string threadID;
        public bool IsRun = false;
        //public bool IsBuildAll = false;
        //public string[] Cookies;
        //public int[] Id;
        //public string[] City;
        //public bool[] Check;
        //public string[][] Building;
        public int Sleep = 60000;
        public Label Message;

		public int mainProcessResult = 0;

		public Hashtable buildUp;   //[cityid, [] building object]

		public ArrayList CityList = new ArrayList();
 
        public BUILD(Label lbl) {
            Message = lbl;
        }
		/*  GetParameter_
		public  void GetParameter_(TreeView tvBUILD, int sleep)
		{
            if (IsRun == false) {

                IsBuildAll = false;
                City = new string[500];
                Id = new int[500];
                Check = new bool[500];
				Building = new string[500][];
				Cookies = new string[500];
                Sleep = sleep;
                //Xay dung cookies
                for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length;i++) {
                    Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(LVClient.Command.CityObj.City.AllCity[i].id);
                    Id[i] = LVClient.Command.CityObj.City.AllCity[i].id;
                }

                //Xay dung mang de xay nha
                TreeNode root = tvBUILD.Nodes["root"];
				root = tvBUILD.Nodes[0];

				if(root.Checked)IsBuildAll=true;
                for (int i = 0; i < root.Nodes.Count; i++) 
				{
                    TreeNode tt = root.Nodes[i];
                    City[i] = tt.Name;

					Building[i] = new string[500];
                    for (int j = 0; j < tt.Nodes.Count; j++) 
					{
						
						if (tt.Nodes[j].Checked) Check[i] = true;

						// "False.30.9.93917" = isbuild.pid.gid.parentid
                       Building[i][j] = tt.Nodes[j].Checked.ToString() + "." + tt.Nodes[j].Name;
                    }
                }
            }
        }
		*/
		
		public void GetParameter( int sleep)
		{
			ArrayList arBuilding ;


			if (IsRun == false)
			{
				buildUp  = new Hashtable();

				/*
				IsBuildAll = false;
				City = new string[500];
				Id = new int[500];
				Check = new bool[500];
				Building = new string[500][];		// [citypost][buildingpost]
				Cookies = new string[500];
				*/

				 Sleep = sleep;
				//Xay dung cookies
				//for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
				//{
				//	Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(LVClient.Command.CityObj.City.AllCity[i].id);
				//	Id[i] = LVClient.Command.CityObj.City.AllCity[i].id;
				//}

				//Xay dung mang de xay nha
			

				bool hasUp = false;
				
				for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
				{
					hasUp = false;
					if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding != null)
					{
						arBuilding = new ArrayList();
						for (int j = 0; j < LVClient.Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
						{
							if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j].isUp)
							{
								arBuilding.Add(LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j]);
								hasUp = true;
							}
						}

						if (hasUp) buildUp.Add(LVClient.Command.CityObj.City.AllCity[i].id, arBuilding);
					}							
				}			

			}
		}
		/*public void run_()
		public void run_()
		{
            IsRun = true;
            while (true) {
                SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
                lock (LVClient.Web.LVWeb.islock) {
                    //lock (LVClient.Web.LVWeb.ispause) {
                        try {
                            SetText("Đang chạy (0%)");
                            for (int i = 0; i < City.Length; i++) {
                                SetText("Đang chạy (" + (i) * 100 / 50 + "%)");
                                if(Check[i] && LVClient.Command.CityObj.City.Canbuild(Id[i])){
                                    try {
                                        Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
                                        LVClient.Command.City.SwitchCitySlow(Id[i]);
                                        if (City[i] != null) {
                                            int buildcount = 0;
                                            for (int j = 0; j < Building[i].Length; j++) {
                                                if (Building[i][j] != null) {
                                                    if (buildcount < 3) {
                                                        string[] info = Building[i][j].Split(new char[] { '.' });
                                                        if (info[0].ToLower() == "true") {
                                                            if (Command.Build.SelectBuilding(Id[i], int.Parse(info[2]), int.Parse(info[1]), 0, Cookies[i]) == false) {
                                                                for (int k = -2; k < 3; k++) {
                                                                    if (Command.Build.SelectBuilding(Id[i], int.Parse(info[2]), int.Parse(info[1]), k, Cookies[i])) {
                                                                        Command.OPT.Build(int.Parse(info[1]), int.Parse(info[2]), int.Parse(info[3]), Cookies[i]);
                                                                        break;
                                                                    };
                                                                }
                                                            } else {
                                                                Command.OPT.Build(int.Parse(info[1]), int.Parse(info[2]), int.Parse(info[3]), Cookies[i]);
                                                            }
                                                            buildcount++;
                                                        }
                                                    }
                                                }
                                            }
                                            //Nap lai danh sach nha
                                            Command.City.GetAllBuilding(i, Cookies[i]);

                                            string[] oldbulding = Building[i];
                                            Building[i] = new string[150];

                                            for (int j = 0; j < Command.CityObj.City.AllCity[i].AllBuilding.Length; j++) {
                                                Command.CityObj.Building onebuilding = Command.CityObj.City.AllCity[i].AllBuilding[j];
                                                //Check thu da duoc check chua
                                                for (int k = 0; k < oldbulding.Length; k++) {
                                                    if (oldbulding[k] != null) {
                                                        string[] info = oldbulding[k].Split(new char[] { '.' }, 2);
                                                        if (info[1] == onebuilding.pid.ToString() + "." + onebuilding.gid.ToString() + "." + City[i]) {
                                                            Building[i][j] = oldbulding[k];
                                                        }
                                                    }
                                                }
                                                //có nhà mới
                                                if (Building[i][j] == null) {
                                                    Building[i][j] = "false." + onebuilding.pid.ToString() + "." + onebuilding.gid.ToString() + "." + City[i];
                                                }
                                            }
                                        }
                                    } catch (Exception ex1) {
                                    }
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
		/*
		public void run1()
		{
			IsRun = true;
			int cityID;
			LVClient.Command.CityObj.City city;
			LVClient.Command.CityObj.Building building;
			bool canBuild = false;

			while (true)
			{
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				lock (LVClient.Web.LVWeb.islock)
				{
					//lock (LVClient.Web.LVWeb.ispause) {
					try
					{
						SetText("Đang chạy (0%)");
						for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
						{
							SetText("Đang chạy (" + (i) * 100 / 50 + "%)");
							city = LVClient.Command.CityObj.City.AllCity[i];
							
							cityID = city.id;

							if (city.citytask == null)  city.citytask = Command.City.GetCityTaskByCityID(cityID);

							try
							{
								canBuild = LVClient.Command.CityObj.City.Canbuild(cityID);
							}
							catch (Exception ex)
							{
								canBuild = false;
							}

							if (canBuild)
							{
								try
								{									
									if (city.AllBuilding != null)
									{
										Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
										LVClient.Command.City.SwitchCitySlow(cityID);

										int buildcount = 0;
										for (int j = 0; j < city.AllBuilding.Length; j++)
										{
											building = city.AllBuilding[j];

											if (building != null)
											{
												if (buildcount < 3)
												{
													//string[] info = Building[i][j].Split(new char[] { '.' });
													if (building.isUp)
													{
														// "False.30.9.93917" = isbuild.pid.gid.parentid
														if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, 0, Cookies[i]) == false)
														{
															for (int k = -2; k < 3; k++)
															{
																if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, k, Cookies[i]))
																{
																	Command.OPT.Build(building.pid, building.gid, cityID, Cookies[i]);
																	break;
																};
															}
														}
														else
														{
															Command.OPT.Build(building.pid, building.gid, cityID, Cookies[i]);
														}
														buildcount++;
													}
												}
											}
										}										
										
									}
								}
								catch (Exception ex1)
								{
								}
							}
						}
					}
					catch (Exception ex)
					{
						//MessageBox.Show(ex.ToString());
					}
					//}
				}
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				//Thread.Sleep(Sleep);
				int ii;
			}
		}
		*/

		private void mainprocess()
        {
#if (DEBUG)
			const int MAXLEVEL = 35;
#else
			const int MAXLEVEL = 33;
#endif

            int cityID;
			int citypos = -1;
			LVClient.Command.CityObj.City city = null;
			LVClient.Command.CityObj.Building building;
			//bool canBuild = false;

			int[] arcityid = null;
			ArrayList arBuilding;
			string cookies;
			int buildcount;

			bool build3 = false;
			int numbuilddoing = 0;

			int citypostocheck = -1;
			Hashtable checkret;
			int maxbuild = 1;
			Hashtable hcitytask;
			ArrayList taskBuild;
			int oldcityid = -1;

			ArrayList arTemp = null;
			bool isBuilding = false;
			
			
			//lock (LVClient.Web.LVWeb.islock)
			{					
				try
				{

					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");
					//LVClient.Command.City.UpdateAllSimpleCity(); //da chay o citytask

					if (LVClient.Command.CityObj.City.isBuildAll)
					{
						buildUp.Clear();
						for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
						{
							Command.City.GetAllBuilding(i,false);

							if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding != null)
							{
								arBuilding = new ArrayList();
								for (int j = 0; j < LVClient.Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
								{									
									arBuilding.Add(LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j]);
								}

								buildUp.Add(LVClient.Command.CityObj.City.AllCity[i].id, arBuilding);
							}
						}
					}




					if (buildUp == null || buildUp.Count == 0)
					{
						SetText("Chẳng có gì để chạy cả");
						return;
					}

					arcityid = new int[buildUp.Count];
					buildUp.Keys.CopyTo(arcityid, 0);

					// check xem duoc xay may cong trinh 1 luc--------
					maxbuild = LVClient.Command.Build.GetMaxNumCanBuild();

					for (int i = 0; i < arcityid.Length; i++)
					{
						try
						{
							cityID = arcityid[i];
							if (cityID != oldcityid)
							{
								citypos = LVClient.Command.City.GetCityPostByID(cityID);
								if (citypos == -1) continue;

								//city = LVClient.Command.City.GetCityByID(cityID);
								city = Command.CityObj.City.AllCity[citypos];


								LVClient.Command.City.UpdateAllBuilding(citypos);
								//city.citytask = Command.City.GetCityTaskByCityID(cityID);

								oldcityid = cityID;
							}


							SetText("Đang chạy: " + city.name + " (đã hoàn thành " + i + "/" + arcityid.Length + " thành. )");

							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
							LVClient.Command.City.SwitchCitySlow(cityID);
							buildcount = 0;

							arBuilding = (ArrayList)buildUp[arcityid[i]];

							hcitytask = Command.City.GetCityTask(cookies);
							if (hcitytask == null) continue;
							taskBuild = (ArrayList)hcitytask["list"];
							buildcount = ((ArrayList)(((ArrayList)taskBuild[0])[4])).Count;				// so luong cong trinh dang xay
							int oldbuildcount = buildcount;

							LVClient.Command.CityObj.Building buildingtmp; 
							//for (int j = 0; j < arBuilding.Count; j++)
							for (int m = 0; m < Command.CityObj.City.AllCity[citypos].AllBuilding.Length; m++ )
							{
								try
								{
									// khoong lam gi neu da xay du con trinh
									if ((maxbuild - buildcount) <= 0) break;

									building = null;
									// tim nha co level thap nhat de xay
									for (int n = 0; n < arBuilding.Count; n++)
									{
										buildingtmp = (LVClient.Command.CityObj.Building) arBuilding[n];
										if (Command.CityObj.City.AllCity[citypos].AllBuilding[m].gid == buildingtmp.gid
											&& Command.CityObj.City.AllCity[citypos].AllBuilding[m].pid == buildingtmp.pid)
										{
											building = Command.CityObj.City.AllCity[citypos].AllBuilding[m];
											break;
										}		  
									}

									if (building == null) continue;
	
									//building = city.AllBuilding[int.Parse(arBuilding[j].ToString())];
									//building = (LVClient.Command.CityObj.Building)arBuilding[j];
									
									if (building.level >= MAXLEVEL) break;



									// check xem cong trinh co dang xay khong
									if (oldbuildcount > 0)
									{
										isBuilding = false;
										// ctrinh dang xay : gid= 3; pid = 18
										for (int k = 0; k < oldbuildcount; k++)
										{
											arTemp = (ArrayList)(((ArrayList)(((ArrayList)taskBuild[0])[4]))[k]);
											if (building.gid == int.Parse(arTemp[1].ToString())
													&& building.pid == int.Parse(arTemp[0].ToString()))
											{
												isBuilding = true;
												break;
											}
										}

										if (isBuilding) continue; 
									}

									int repeat = 0;
									Hashtable result = null;
									while (true && repeat < 3)
									{
									
										// "False.30.9.93917" = isbuild.pid.gid.parentid
										if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, 0, cookies) == false)
										{
											for (int k = -2; k < 3; k++)
											{
												if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, k, cookies))
												{
													result = Command.OPT.Build(building.pid, building.gid, cityID, cookies);
													break;
												};
											}
										}
										else
										{
											result = Command.OPT.Build(building.pid, building.gid, cityID, cookies);
										}

										//int ret = 0;
										//32: thieu tai nguyen	sat

										if (result == null)  // fail
										{
											mainProcessResult = -1;
											break;
										}
										else
										{

											mainProcessResult = int.Parse(result["ret"].ToString());
										  											
											
											if (mainProcessResult == 110)		  // bi check anh, can lam lai
											{
												break;
											}

											if (mainProcessResult == 0)   // thanh cong
											{
												buildcount++;   // tang so luong cong trinh dang xay
												break;
											}
											if (mainProcessResult > 1000000) // bi lock
											{
												return;
											}

											if (mainProcessResult == 32)	 // thieu tai nguyen
											{	
												if (cityID < 0)  // trai
												{
													buildcount++;   // tang so luong cong trinh dang xay, toi da tim xay 3 cong trinh khi thieu tai nguyen
													break;
												}
												else
												{
													if (Command.CityObj.City.isBuyRes)
														if (MuaThemTaiNguyen(cityID, building.gid, building.pid, Command.CityObj.City.goldSafe, cookies))
														{
															// tiep tuc mua lai
															repeat++;
															continue;
														}	
												}
											}
										}
											  
										break;
									} // while (true)

								}

								catch (Exception ex) { }

								//Array.Sort((arBuilding.ToArray()));

							}	 //end for (int m = 0; m < Command.CityObj.City.AllCity[citypos].AllBuilding.Length; m++ )

						}
						catch (Exception ex)
						{
						}
					}   // end for city
				}
				catch (Exception ex)
				{
					//MessageBox.Show(ex.ToString());
				}
				//}
			}
		}

		private bool MuaThemTaiNguyen(int cityid, int gid, int pid, long safegold, string cookies)
		{
			try
			{
				Hashtable ResNeed = Command.Build.getResourceNeedForUpgradeBuilding(gid, pid, cookies);				

				Hashtable ResHave = Command.City.GetCurentResourceInCity(cookies);

				//long safegold = 5000000;

				int needValue;
				int haveValue;
				int needbuy;
				int maxkho = int.Parse(ResHave["MAXKHO"].ToString());
				long gold = long.Parse(ResHave["GOLD"].ToString());
				gold = gold - safegold;
				if (gold <= 0) return false;		// khong du vang

				needValue = int.Parse( ResNeed["LUA"].ToString());
				haveValue = int.Parse(ResHave["LUA"].ToString());

				if (needValue > maxkho) return false;		// khong du kho 

				if (needValue > haveValue)
				{
					needbuy = needValue - haveValue;
					Command.OPT.BuyRes(Common.Constant.RESOURCETYPE.LUA, (double)needbuy, ref gold, cookies);
							   
				}

				needValue = int.Parse(ResNeed["GO"].ToString());
				haveValue = int.Parse(ResHave["GO"].ToString());

				if (needValue > maxkho) return false;		// khong du kho 

				if (needValue > haveValue)
				{
					needbuy = needValue - haveValue;
					Command.OPT.BuyRes(Common.Constant.RESOURCETYPE.GO, (double)needbuy, ref gold, cookies);

				}

				needValue = int.Parse(ResNeed["DA"].ToString());
				haveValue = int.Parse(ResHave["DA"].ToString());

				if (needValue > maxkho) return false;		// khong du kho 

				if (needValue > haveValue)
				{
					needbuy = needValue - haveValue;
					Command.OPT.BuyRes(Common.Constant.RESOURCETYPE.DA, (double)needbuy, ref gold, cookies);

				}
				needValue = int.Parse(ResNeed["SAT"].ToString());
				haveValue = int.Parse(ResHave["SAT"].ToString());

				if (needValue > maxkho) return false;		// khong du kho 

				if (needValue > haveValue)
				{
					needbuy = needValue - haveValue;
					Command.OPT.BuyRes(Common.Constant.RESOURCETYPE.SAT, (double)needbuy, ref gold, cookies); 
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
				if (!LVClient.Command.CityObj.City.isBuildAll && ( buildUp == null || buildUp.Count == 0))
				{
					SetText("Chẳng có gì để chạy cả");
					break;
				}
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "BUILD_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID , mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				if (mainProcessResult > 1000000)
				{
					SetText("Bị khóa đến " + DateTime.Now.AddSeconds(mainProcessResult - 1000000).ToString("HH:mm:ss")  
						+  ". Đang ngủ " + Sleep / (1000 * 60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
				}
				Thread.Sleep(Sleep);
				
			}
		}
		public void Auto()
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true;  InThread.Start();
			}
		}
		public  void Stop()
		{
            if (IsRun) {
                InThread.Abort();
                InThread.Join();
				Common.ThreadManager.RemoveThread(threadID);
                Message.ForeColor = System.Drawing.Color.Blue ; Message.Text = "Đã dừng bởi người sử dụng";
                IsRun = false;
            }
        }
		public  void SetText(String str)
		{
            if (this.Message.InvokeRequired) {
                SetTextCallback d = new SetTextCallback(SetText);
                this.Message.Invoke(d, new object[] { str });
            } else {
                this.Message.Text = str;
            }
        }
    }
}
