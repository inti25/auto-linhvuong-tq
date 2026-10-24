using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;
using System.Data;

namespace LVClient.LVThread {
    public class UPGRADE {
        delegate void SetTextCallback(string text);
        public Thread InThread; 
		public string threadID;
        public bool IsRun = false;
        //public string[] Cookies;
        public string[] tech;
        //public int[] Id;
        public int techcount;
        public int Sleep = 60000;
        public Label Message;

		private int cityid;
		private int nexttech = 0;
        public UPGRADE(Label lbl) 
		{
            Message = lbl;
        }
        /*public void GetParameter1(TreeView tvUpdate, int ctyid, int sleep) {
            if (IsRun == false) {

                Cookies = new string[50];
                tech = new string[50];
                Id = new int[50];
                this.Sleep = sleep;

                //Xay dung cookies
                Cookies[0] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(ctyid);
                Id[0] = ctyid;
                techcount = 0;
                TreeNode root = tvUpdate.Nodes["root"];
                foreach (TreeNode t in root.Nodes) {
                    foreach (TreeNode c in t.Nodes) {
                        if (c.Checked) {
                            tech[techcount] = c.Name;
                            techcount++;
                        }
                    }
                }
            }
        }*/

		public void GetParameter(ArrayList upgradedata, int sleep)
		{
			if (IsRun == false)
			{

				//Cookies = new string[50];
				tech = new string[upgradedata.Count-1];
				//Id = new int[50];
				this.Sleep = sleep;

				//Xay dung cookies
				//Cookies[0] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(ctyid);
				cityid = int.Parse( upgradedata[0].ToString()); ;
				int citypos = LVClient.Command.City.GetCityPostByID(cityid);
				if (citypos == -1)
				{
					SetText("Chưa chọn thành chính");
					return;
				}

				techcount = upgradedata.Count-1;
				for (int i = 1; i < upgradedata.Count; i++)
				{
					tech[i - 1] = upgradedata[i].ToString();
				}

				/*
				TreeNode root = tvUpdate.Nodes["root"];
				foreach (TreeNode t in root.Nodes)
				{
					foreach (TreeNode c in t.Nodes)
					{
						if (c.Checked)
						{
							tech[techcount] = c.Name;
							techcount++;
						}
					}
				}
				 */ 
			}
		}

		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				Hashtable result;
				LVClient.Command.CityObj.CityTask citytask;
				string cookies;
				int ret;
				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");

					for (int techindex = 0; techindex < techcount; techindex++)			// duyeetj het cac hang muc can nang cap
					{
						for (int cityindex = 0; cityindex < Command.CityObj.City.AllCity.Length; cityindex++)		// duyet het cac thanh
						{
							if (Command.CityObj.City.AllCity[cityindex].id < 0) continue;	// trại bỏ qua

							cityid = Command.CityObj.City.AllCity[cityindex].id;
							citytask = LVClient.Command.City.GetCityTaskByCityID(cityid);

							if (!citytask.Canupgrade)				// citytask.Canupgrade= false: ddang co nghien cuu, khong lam nua
								return;

							//if(LVClient.Command.CityObj.City.Canupgrade(Id[0]))
							//if (citytask.Canupgrade)				// citytask.Canupgrade= false: ddang co nghien cuu, khong lam nua
							//{
								if (nexttech < techcount)
								{
									cookies = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cityid);

									LVClient.Command.City.SwitchCitySlow(cityid);


									if (Command.Build.SelectBuilding(cityid, 6, cookies))
									{
										int count = 0;
										do
										{
											result = Command.OPT.Upgrade(int.Parse(tech[nexttech]), cookies);
											count++;
										} while (result == null && count < 5);

										if (result == null) continue;	// looi

										ret = int.Parse(result["ret"].ToString());
										if (ret == 245)			// khong du dieu kien de nang hoac dang co cong trinh dang nang
										{}

										if (ret != 0)
											continue;
										else                  // ok
										{
											break;
										}
									}  //end if (Command.Build.SelectBuilding(cityid, 6, cookies))
								}	//if (nexttech < techcount)
							//}  // if (citytask.Canupgrade)
						} //end for (int cityindex=0; cityindex < Command.CityObj.City.AllCity.Length; cityindex++)

						nexttech++;
						if (nexttech >= techcount) nexttech = 0;

					} // end for (int techindex = 0; techindex < techcount; techindex++)	
				} //try
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
				threadID = "UPGRADE_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun( threadID, mainprocess);
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
