using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

namespace LVClient.LVThread {
    public class MOVEDOANHTRAI {
        delegate void SetTextCallback(string text);
        public Thread InThread; 
		public string threadID;
        public bool IsRun = false;

		ArrayList TraiDiChuyen;

		//public string[] Cookies;
        //public int[][] Pos;
        //public int citycount;
        public int Sleep = 60000;
        
		//public int[] Id;

        public Label Message;
        public MOVEDOANHTRAI(Label lbl) 
		{
            Message = lbl;
        }
        /*public void GetParameter(Panel pnDoanhTrai, int sleep) 
		{
            if (IsRun == false) {
                citycount = 0;
                Cookies = new string[50];
                Pos = new int[50][];
                Id = new int[50];
                this.Sleep = sleep;
                foreach (object obj in pnDoanhTrai.Controls) {
                    LVClient.Command.CommonObj.doitrai vc = (LVClient.Command.CommonObj.doitrai)obj;
                    if (vc.chkOK.Checked) {
                        Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(vc.id);
                        Pos[citycount] = new int[3];
                        Pos[citycount][0] = int.Parse(vc.X.Text);
                        Pos[citycount][1] = int.Parse(vc.Y.Text);
                        Pos[citycount][2] = vc.id;
                        Id[citycount] = vc.id;
                        citycount++;
                    }
                }
            }
        }
		 */
		
		public void GetParameter(ArrayList traidichuyen, int sleep)
		{
			if (IsRun == false)
			{
				this.Sleep = sleep;
				this.TraiDiChuyen = traidichuyen;

			}
		}

		/*private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");
					Hashtable hsTemp = null;
					int maxsteps = 3;
					ArrayList runningstep = new ArrayList();
					for (int i = 0; i < citycount; i++)
					{
						SetText("Đang chạy... (" + i + "/" + citycount + ")");
						try
						{
							Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
							LVClient.Command.City.SwitchCitySlow(Id[i]);

							// lay thong tin trong hang cho
							hsTemp = LVClient.Command.Common.Execute(80, "tid=" + Id[i], true, Cookies[i]);
							if (hsTemp == null && int.Parse(hsTemp["ret"].ToString()) != 0) continue;

							if (long.Parse(hsTemp["plus_left"].ToString()) > 0) maxsteps = 6;
							runningstep = (ArrayList)hsTemp["path"];
							if (runningstep.Count >= maxsteps) continue;		// da du trong hang doi, khong lam gi nua

							Command.CityObj.City thisdt = null;
							if (runningstep.Count > 0)
							{
								// laays trong hang cho
								int mapID = int.Parse( runningstep[runningstep.Count - 1].ToString());
								int x = Command.Common.MapIDtoX(mapID);
								int y = Command.Common.MapIDtoY(mapID);
								thisdt = new LVClient.Command.CityObj.City(Id[i], "", x, y);
							}
							else
							{
								// lay toa do cua trai
								thisdt = Command.City.GetCityInfo(Pos[i][2], Cookies[i]);
							}

							if (thisdt == null) continue;

							if (thisdt.x == Pos[i][0] && thisdt.y == Pos[i][1])
							{

							}
							else
							{
								int tarX = Pos[i][0];
								int tarY = Pos[i][1];
								int step;
								for (int c = 0; c < 5; c++)
								{
									for (step = 16; step > 0; step--)
									{
										//int[] xy = Common.common.NextPoint(thisdt.x, thisdt.y, Pos[i][0], Pos[i][1], step);
										int[] xy = Common.common.NextPoint(thisdt.x, thisdt.y, tarX, tarY, step);
										int ret = Command.Common.MoveDT(xy[0], xy[1], Pos[i][2], Cookies[i]);
										if (ret == 0 || ret == 1)
										{
											break;
										}
									}
									if (step > 0) break;	// di chuyen thanh cong

									tarX += 30;
									tarY += 20;

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
		   */
		private void mainprocess()
		{
				try
				{
					if (TraiDiChuyen == null || TraiDiChuyen.Count <= 0)
					{
						frmmain.LVFRMMAIN.lblMOVEDOANHTRAI.Text = "chẳng có cái trại nào cần chuyển cả";
						return;
					}
					
					Message.ForeColor = System.Drawing.Color.Red;
					SetText("Đang chạy (0%)");
					Hashtable hsTemp = null;
					int maxsteps = 3;
					ArrayList runningstep = new ArrayList();
					Command.CommonObj.DoiTraiObj traidichuyenobj;
					string cookies;
					for (int i = 0; i < TraiDiChuyen.Count; i++)
					{
						traidichuyenobj = (Command.CommonObj.DoiTraiObj) TraiDiChuyen[i];
						SetText("Đang chạy " + traidichuyenobj.TraiName + "(" + i + "/" + TraiDiChuyen.Count  + ")");
						try
						{
							cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(traidichuyenobj.TraiID);
							LVClient.Command.City.SwitchCitySlow(traidichuyenobj.TraiID);

							// lay thong tin trong hang cho
							hsTemp = LVClient.Command.Common.Execute(80, "tid=" + traidichuyenobj.TraiID, true, cookies);
							if (hsTemp == null && int.Parse(hsTemp["ret"].ToString()) != 0) continue;	 // bi loi gi do

							if (long.Parse(hsTemp["plus_left"].ToString()) > 0) maxsteps = 6;
							runningstep = (ArrayList)hsTemp["path"];
							if (runningstep.Count >= maxsteps) continue;		// da du trong hang doi, khong lam gi nua

							Command.CityObj.City thisdt = null;
							if (runningstep.Count > 0)
							{
								// laays trong hang cho
								int mapID = int.Parse(runningstep[runningstep.Count - 1].ToString());
								int x = Common.common.MapIDtoX(mapID);
								int y = Common.common.MapIDtoY(mapID);
								thisdt = new LVClient.Command.CityObj.City(traidichuyenobj.TraiID, "", x, y, 1);
							}
							else
							{
								// lay toa do cua trai
								thisdt = Command.City.GetCityInfo(traidichuyenobj.TraiID, cookies);
							}

							if (thisdt == null) continue;

							if (thisdt.x == traidichuyenobj.targetX && thisdt.y == traidichuyenobj.targetY)
							{
								if (runningstep.Count == 0)
									removetraifromlist(i);
							}
							else
							{
								int tarX = traidichuyenobj.targetX;
								int tarY = traidichuyenobj.targetY;
								int step;
								int c;
								int lastx = 0;
								int lasty = 0;
								int ret = -1;
								for (c = 0; c < 3; c++)
								{
									for (step = 16; step > 0; step--)
									{
										//int[] xy = Common.common.NextPoint(thisdt.x, thisdt.y, Pos[i][0], Pos[i][1], step);
										int[] xy = Common.common.NextPoint(thisdt.x, thisdt.y, tarX, tarY, step);
										if (xy[0] == lastx && xy[1] == lasty)
										{
										}
										else
										{
											ret = Command.Common.MoveDT(xy[0], xy[1], traidichuyenobj.TraiID, cookies);
											lastx = xy[0];
											lasty = xy[1];
										}

										if (ret == 0 || ret == 1)
										{
											break;
										}
									}
									if (step > 0) break;	// di chuyen thanh cong

									if (Common.common.distancefrom2poin(thisdt.x, thisdt.y, tarX, tarY) <= 5) // gan toi, cach 5 o
									{
										if (runningstep.Count == 0)
										{
											removetraifromlist(i);
											
											break;
										}
									}


									if (c == 0)
									{
										tarX += 5;
										tarY += 5;
									}
									else
									{
										tarX -= 10;
										tarY -= 10;
									}
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

		
		private void removetraifromlist(int listpost)
		{
			int traiID = ((Command.CommonObj.DoiTraiObj)TraiDiChuyen[listpost]).TraiID;

			LVClient.Command.CommonObj.doitrai vc;

			foreach (object obj in frmmain.LVFRMMAIN.pnDoanhTrai.Controls)
			{
				vc = (LVClient.Command.CommonObj.doitrai)obj;
				if (vc.id == traiID)
				{
					vc.chkOK.Checked = false;
					break;
				}
			} 

			TraiDiChuyen.RemoveAt(listpost);
		}

		public void run() 
		{
            IsRun = true;
            while (true) 
			{
                SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "MOVEDOANHTRAI_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");
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
                InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
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
