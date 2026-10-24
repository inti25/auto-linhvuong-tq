using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread {
    public class BUYWEPON {
        delegate void SetTextCallback(string text);
        public Thread InThread; public string threadID;
        public bool IsRun = false;
        public string[] Cookies;
        public int[][] City;
        public int[] Id;
        public int citycount;
        public int Sleep = 60000;
        public int unit;
        public Label Message;
		public int mainProcessResult = 0;

        public BUYWEPON(Label lbl) {
            Message = lbl;
        }
        public void GetParameter(int unit, Panel pnWepon, int sleep) {
            if (IsRun == false) {

                Cookies = new string[500];
                City = new int[500][];
                Id = new int[500];
                this.Sleep = sleep;
                this.unit = unit;
                //Xay dung cookies
                citycount = 0;

                foreach (object obj in pnWepon.Controls) 
				{
                    LVClient.Command.OPTObj.wepon vc = (LVClient.Command.OPTObj.wepon)obj;
                    if (vc.chkOK.Checked) 
					{
                        Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(vc.cityid);
                        Id[citycount] = vc.cityid;
                        City[citycount] = new int[9];
                        City[citycount][0] = vc.cboWepon.Text == "" ? 0 : int.Parse(vc.cboWepon.Text.Split(new Char[] { '.' })[0]);
                        City[citycount][1] = vc.cboAmor.Text==""?0:int.Parse(vc.cboAmor.Text.Split(new Char[] { '.' })[0]);
                        City[citycount][2] = vc.cboHorse.Text == "" ? 0 : int.Parse(vc.cboHorse.Text.Split(new Char[] { '.' })[0]);
                        City[citycount][3] = vc.txtAmount.Text == "" ? 0 : int.Parse(vc.txtAmount.Text);	// so luong max
                        City[citycount][4] = vc.cboLevel.Text == "" ? 0 : int.Parse(vc.cboLevel.Text);
                        City[citycount][5] = vc.posid_w; //pid
                        City[citycount][6] = vc.posid_a;
                        City[citycount][7] = vc.posid_h;
						City[citycount][8] = 0;				// flag đánh dấu sẽ mua loại vu khi nao tiếp theo

                        citycount++;
                    }
                }
            }
        }

		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				int citypos;
				int rd = (new Random()).Next(2);
				Hashtable result = null;
				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");
					for (int i = 0; i < citycount; i++)
					{
						// SetText("Đang chạy (" + i + " / " + citycount + ")");
						try
						{
							Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
							LVClient.Command.City.SwitchCitySlow(Id[i]);

							citypos = LVClient.Command.City.GetCityPostByID(Id[i]);
							//---
							// lay lai thong tin neu truoc chua lay duoc
							if (City[i][5] <= 0 || City[i][6] <= 0 || City[i][7] <= 0)
							{


								if (Command.CityObj.City.AllCity[citypos].AllBuilding == null)
									LVClient.Command.City.GetAllBuilding(i, false, Cookies[i]);

								if (Command.CityObj.City.AllCity[citypos].AllBuilding == null)
								{
									continue;
								}
								else
								{
									City[i][5] = 0;
									City[i][6] = 0;
									City[i][7] = 0;

									//Lay nha vu khi
									for (int j = 0; j < Command.CityObj.City.AllCity[citypos].AllBuilding.Length; j++)
									{
#if (DEBUG)
                                        if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 13
                                            || Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 66                                            
                                            )// xuong binh khi
#else
	
                                        if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 13)// xuong binh khi
#endif
                                        {
											City[i][5] = Command.CityObj.City.AllCity[citypos].AllBuilding[j].pid;
										}


#if (DEBUG)
                                        if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 14
                                            || Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 67                                            
                                            )// xuong binh khi
#else
										if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 14) //Xuong khoi giap
#endif										
                                        
                                        {
											City[i][6] = Command.CityObj.City.AllCity[citypos].AllBuilding[j].pid;
										}
										
#if (DEBUG)
                                        if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 15
                                            || Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 68                                            
                                            )// xuong binh khi
#else

                                        if (Command.CityObj.City.AllCity[citypos].AllBuilding[j].gid == 15) // xuong ma xa
#endif
                                        {
											City[i][7] = Command.CityObj.City.AllCity[citypos].AllBuilding[j].pid;
										}
									}
								}
							}
							//---------------

							result = null;
							SetText("Đang chạy " + Command.CityObj.City.AllCity[citypos].name + " (" + i + "/" + citycount + ")");
							int index;
                            int indtemp=13;
#if (DEBUG)
                                    if (Command.CityObj.City.AllCity[citypos].size == 4) indtemp = 66;
#endif
							for (int k = 0; k < 3; k++)
							{
								index = City[i][8];
								if (City[i][index] > 0 && City[i][3] > 0)	
								{
                                    
#if (DEBUG)
                                    if (Command.Build.SelectBuilding(Id[i], index + indtemp, Cookies[i]))
#else
									if (Command.Build.SelectBuilding(Id[i], index + 13, Cookies[i]))
#endif
									{
										result = Command.OPT.Buywepon(City[i][index], unit, City[i][4], City[i][index + 5], Cookies[i]);
										if (result != null)
										{
											if (int.Parse(result["ret"].ToString()) == 0)
											{
												City[i][3] -= unit;

												if (City[i][8] == 2)
													City[i][8] = 0;
												else
													City[i][8]++;
											}
											if (int.Parse(result["ret"].ToString()) == 32)		// thieu tai nguyen
											{
												break;
											}

										}
									}
								} // 								if (City[i][index] > 0 && City[i][3] > 0)	
								else
								{
									if (City[i][8] == 2)
										City[i][8] = 0;
									else
										City[i][8]++; 
								}
							}
							
							/*
							rd = (new Random()).Next(2);
							if (rd == 0)		// lay ngau nhien
							{
								//rd = 1;
								if (City[i][0] > 0 && City[i][3] > 0)	// cung
								{
									if (Command.Build.SelectBuilding(Id[i], 13, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][0], unit, City[i][4], City[i][5], Cookies[i]);
										
									}
								}

								if (City[i][2] > 0 && City[i][3] > 0)
								{
									if (Command.Build.SelectBuilding(Id[i], 15, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][2], unit, City[i][4], City[i][7], Cookies[i]);
									}
								}
								if (City[i][1] > 0 && City[i][3] > 0)	//giap
								{
									if (Command.Build.SelectBuilding(Id[i], 14, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][1], unit, City[i][4], City[i][6], Cookies[i]);
									}
								}
							}
							else
							{
								//rd = 0;
								if (City[i][1] > 0 && City[i][3] > 0)			// giap
								{
									if (Command.Build.SelectBuilding(Id[i], 14, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][1], unit, City[i][4], City[i][6], Cookies[i]);
									}
								}

								if (City[i][2] > 0 && City[i][3] > 0)		// ngua
								{
									if (Command.Build.SelectBuilding(Id[i], 15, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][2], unit, City[i][4], City[i][7], Cookies[i]);
									}
								}


								if (City[i][0] > 0 && City[i][3] > 0)		// cung
								{
									if (Command.Build.SelectBuilding(Id[i], 13, Cookies[i]))
									{
										result = Command.OPT.Buywepon(City[i][0], unit, City[i][4], City[i][5], Cookies[i]);
									}
								}
							}
							*/

							//City[i][3] -= unit;

							if (result == null)  // fail
							{
							}
							else
							{
								mainProcessResult = int.Parse(result["ret"].ToString());
								if (mainProcessResult == 32)		// thiếu tài nguyên
								{
								}
								if (mainProcessResult > 1000000) // bi lock
								{
									return;
								}
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
				threadID = "BUYWEPON_" + DateTime.Now.Ticks;
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
                Message.ForeColor = System.Drawing.Color.Blue ; Message.Text = "Đã dừng bởi người sử dụng";
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
