using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread {
    public class DEL {

		
        delegate void SetTextCallback(string text);
		public  Thread InThread;
		public string threadID;
		public  bool IsRun = false;
		//public  bool IsBuildAll = false;
		//public  string[] Cookies;
		//public  int[] Id;
		//public  string[] City;
		//public  bool[] Check;
		//public  string[][] Building;
		public  int Sleep = 60000;
		public  Label Message;

		public int mainProcessResult = 0;

		public Hashtable buildDown;
        
		public DEL(Label lbl) 
		{
            Message = lbl;
        }

		/* public   void GetParameter1(TreeView tvBUILD,int sleep) {
			 if (IsRun == false) {

				 IsBuildAll = false;
				 City = new string[50];
				 Id = new int[50];
				 Check = new bool[50];
				 Building = new string[50][];
				 Cookies = new string[50];
				 Sleep = sleep;
				 Xay dung cookies
				 for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length;i++) {
					 Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(LVClient.Command.CityObj.City.AllCity[i].id);
					 Id[i] = LVClient.Command.CityObj.City.AllCity[i].id;
				 }

				 //Xay dung mang de xay nha
				 TreeNode root = tvBUILD.Nodes["root"];
				 if(root.Checked)IsBuildAll=true;

				 for (int i = 0; i < root.Nodes.Count; i++) {
					 TreeNode tt = root.Nodes[i];
					 City[i] = tt.Name;
                    
					 Building[i] = new string[50];
					 for (int j = 0; j < tt.Nodes.Count; j++) {
						 if (tt.Nodes[j].Checked) Check[i] = true;
						 Building[i][j] = tt.Nodes[j].Checked.ToString() + "." + tt.Nodes[j].Name;
					 }
				 }
			 }
		 }
		  */ 
		public void GetParameter(TreeView tvBUILD, int sleep)
		{
			ArrayList arBuilding;


			if (IsRun == false)
			{
				buildDown = new Hashtable();

				
				//IsBuildAll = false;
				//City = new string[500];
				//Id = new int[500];
				//Check = new bool[500];
				
				//Building = new string[500][];		// [citypost][buildingpost]
				//Cookies = new string[500];
				Sleep = sleep;
				


				bool hasDown = false;

				for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
				{
					hasDown = false;
					if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding != null)
					{
						arBuilding = new ArrayList();
						for (int j = 0; j < LVClient.Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
						{
							if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j].isDown)
							{
								//arBuilding.Add(j);
								arBuilding.Add(LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j]);
								hasDown = true;
							}
						}

						if (hasDown) buildDown.Add(LVClient.Command.CityObj.City.AllCity[i].id, arBuilding);	//buildDown.Add(i, arBuilding);
					}
				}

			}
		}

		/** public  void run1()		 
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
                                                                        Command.OPT.Build(int.Parse(info[1]), int.Parse(info[2]), int.Parse(info[3]),2, Cookies[i]);
                                                                        break;
                                                                    };
                                                                }
                                                            } else {
                                                                Command.OPT.Build(int.Parse(info[1]), int.Parse(info[2]), int.Parse(info[3]),2, Cookies[i]);
                                                            }
                                                            buildcount++;
                                                        }
                                                    }
                                                }
                                            }
                                            //Nap lai danh sach nha
                                            Command.City.GetAllBuilding(i, Cookies[i]);

                                            string[] oldbulding = Building[i];
                                            Building[i] = new string[50];

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


		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					int cityID;
					LVClient.Command.CityObj.City city;
					LVClient.Command.CityObj.Building building;
					bool canBuild = false;

					int[] arcityid = null;
					ArrayList arBuilding;
					string cookies;
					int maxbuild = 1;
					Hashtable hcitytask;
					ArrayList taskBuild;
					bool found;
					int citypos;
					bool isBuilding;
					ArrayList arTemp = null;

					SetText("Đang chạy (0%)");
					//LVClient.Command.City.UpdateAllSimpleCity();

					if (LVClient.Command.CityObj.City.isDowndAll)
					{
						buildDown.Clear();
						for (int i = 0; i < LVClient.Command.CityObj.City.AllCity.Length; i++)
						{
							Command.City.GetAllBuilding(i, false);

							if (LVClient.Command.CityObj.City.AllCity[i].AllBuilding != null)
							{
								arBuilding = new ArrayList();
								for (int j = 0; j < LVClient.Command.CityObj.City.AllCity[i].AllBuilding.Length; j++)
								{
									arBuilding.Add(LVClient.Command.CityObj.City.AllCity[i].AllBuilding[j]);
								}

								buildDown.Add(LVClient.Command.CityObj.City.AllCity[i].id, arBuilding);
							}
						}
					}

					
					
					if (buildDown == null || buildDown.Count <= 0)
					{
						SetText("Chẳng có gì để chạy cả");
						return;
					}

					arcityid = new int[buildDown.Count];
					buildDown.Keys.CopyTo(arcityid, 0);

					// check xem duoc xay may cong trinh 1 luc--------
					maxbuild = LVClient.Command.Build.GetMaxNumCanBuild();

					int buildcount;
					for (int i = 0; i < arcityid.Length; i++)
					{
						try
						{
							cityID = arcityid[i];

							citypos = LVClient.Command.City.GetCityPostByID(cityID);
							//city = LVClient.Command.City.GetCityByID(cityID);
							city = LVClient.Command.CityObj.City.AllCity[citypos];

							if (city == null) continue;
							SetText("Đang chạy: " + city.name + " (đã hoàn thành " + i + "/" + arcityid.Length + " thành. )");

							LVClient.Command.City.SwitchCitySlow(cityID);

							//city.citytask = Command.City.GetCityTaskByCityID(cityID);
							LVClient.Command.City.UpdateAllBuilding(citypos);


							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityID);
							buildcount = 0;
							arBuilding = (ArrayList)buildDown[arcityid[i]];


							hcitytask = Command.City.GetCityTask(cookies);
							if (hcitytask == null) continue;
							taskBuild = (ArrayList)hcitytask["list"];
							buildcount = ((ArrayList)(((ArrayList)taskBuild[0])[4])).Count;				// so luong cong trinh dang xay
							int oldbuildcount = buildcount;

							LVClient.Command.CityObj.Building buildingtmp;
							
							//for (int j = arBuilding.Count - 1; j >= 0; j--)
							for (int m = Command.CityObj.City.AllCity[citypos].AllBuilding.Length - 1; m >= 0; m--)
							{


								// khoong lam gi neu da xay du con trinh
								if ((maxbuild - buildcount) <= 0) break;


								//building = (LVClient.Command.CityObj.Building)arBuilding[j];
								building = null;
								// tim nha co level cao nhat de ha
								for (int n = 0; n < arBuilding.Count; n++)
								{
									buildingtmp = (LVClient.Command.CityObj.Building)arBuilding[n];
									if (Command.CityObj.City.AllCity[citypos].AllBuilding[m].gid == buildingtmp.gid
										&& Command.CityObj.City.AllCity[citypos].AllBuilding[m].pid == buildingtmp.pid)
									{
										building = Command.CityObj.City.AllCity[citypos].AllBuilding[m];
										break;
									}
								}

								if (building == null) continue;



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


								Hashtable result = null;

								//if (buildcount < 5)
								{
									//string[] info = Building[i][j].Split(new char[] { '.' });

									// "False.30.9.93917" = isbuild.pid.gid.parentid
									if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, 0, cookies) == false)
									{
										for (int k = -2; k < 3; k++)
										{
											if (Command.Build.SelectBuilding(cityID, building.gid, building.pid, k, cookies))
											{
												result = Command.OPT.Build(building.pid, building.gid, cityID, 2, cookies);
												break;
											};
										}
									}
									else
									{
										result = Command.OPT.Build(building.pid, building.gid, cityID, 2, cookies);
									}


									if (result == null)  // fail
									{
										mainProcessResult = -1;
									}
									else
									{

										mainProcessResult = int.Parse(result["ret"].ToString());

										if (mainProcessResult == 0)   // thanh cong
										{
											buildcount++;
										}
										if (mainProcessResult > 1000000) // bi lock
										{
											return;
										}
									}

								}
							}   // end for building
							//Array.Sort((arBuilding.ToArray()));
						}						 
						catch (Exception ex)
						{
						}
					}		// end for city
				}
				catch (Exception ex)
				{
					//MessageBox.Show(ex.ToString());
				}
				//}
			}
		}
		public void run()
		{


			IsRun = true;
			
			while (true)
			{
				if (buildDown == null || buildDown.Count <= 0)
				{
					SetText( "Chẳng có gì để chạy cả");
					break;
				}
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "DEL_" + DateTime.Now.Ticks;
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
                InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
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
