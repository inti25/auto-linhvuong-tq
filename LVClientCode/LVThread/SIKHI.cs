using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;
namespace LVClient.LVThread {
    public class SIKHI 
	{
        delegate void SetTextCallback(string text);
        public Thread InThread; public string threadID;
        public bool IsRun = false;
        public string[] Cookies;
        public int[] General;
        public int[] Id;
        public int citycount;
        public int Sleep = 60000;
        public int addsikhi = 10;
        public Label Message;

        public SIKHI(Label lbl) 
		{
            Message = lbl;
        }
        public void GetParameter(TreeView tvSIKHI, int addsikhi, int sleep) 
		{
            if (IsRun == false) {

                Cookies = new string[50];
                Id = new int[50];
                General = new int[50];
                this.Sleep = sleep;
                this.addsikhi = addsikhi;
                //Xay dung cookies
                citycount = 0;

                TreeNode root = tvSIKHI.Nodes["root"];
                for (int i = 0; i < root.Nodes.Count; i++) 
				{
                    TreeNode g = root.Nodes[i];
                    if (g.Checked) {
                        string[] ginfo = g.Name.Split(new char[] { '.' });
                        Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(int.Parse(ginfo[0]));
                        Id[citycount] = int.Parse(ginfo[0]);
                        General[citycount] = int.Parse(ginfo[1]);
                        citycount++;
                    }
                }
            }
        }

		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{

				try
				{
					Message.ForeColor = System.Drawing.Color.Red; 
					SetText("Đang chạy (0%)");
                    int citypost;
					for (int i = 0; i < citycount; i++)
					{
						SetText("Đang chạy (" + (i) * 100 / citycount + "%)");
						try
						{
                            citypost = LVClient.Command.City.GetCityPostByID(Id[i]);

							Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
							LVClient.Command.City.SwitchCitySlow(Id[i]);

							// da duoc check khi luyen
							//sk = Command.Common.GetGeneralSyKhiInLuyenBinh(Id[i], General[i]);

							//if (sk < 100)
							{

								if (Id[i] > 0)
								{
                                    int gid=16;
#if (DEBUG)
                                    if (LVClient.Command.CityObj.City.AllCity[citypost].size == 4) gid = 69;
#endif                                    

									if (Command.Build.SelectBuilding(Id[i], gid, Cookies[i]))
									{
										Command.OPT.UpSiKhi(Id[i], General[i], addsikhi);
									}
								}
								else
								{
									if (Command.Build.SelectBuilding(Id[i], 19, Cookies[i]))
									{
										Command.OPT.UpSiKhi(Id[i], General[i], addsikhi);
									}
								}
							}
						}
						catch (Exception exx1)
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
		public void run() {
            IsRun = true;
		
			while (true) 
			{
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "SIKHI_" + DateTime.Now.Ticks;
				Common.ThreadManager.TakeResourceAndRun(threadID , mainprocess);
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
        private void SetText(String str) 
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
