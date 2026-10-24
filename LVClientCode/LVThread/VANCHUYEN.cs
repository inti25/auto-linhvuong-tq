using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Data;
using System.Collections;

namespace LVClient.LVThread {
    public class VANCHUYEN {
        delegate void SetTextCallback(string text);
        public Thread InThread; 
		public string threadID;
        public bool IsRun = false;
        public string[] Cookies;
        public int[][] City;
        public int[] Id;
        public int citycount;
        public int Sleep = 60000;
        public Label Message;
        public VANCHUYEN(Label lbl) 
		{
            Message = lbl;
        }
        public void GetParameter(Panel pnVanchuyen, int sleep) {
            if (IsRun == false) {
                citycount = 0;
                Cookies = new string[500];
                City = new int[500][];
                Id = new int[500];
                this.Sleep = sleep;
				LVClient.Command.OPTObj.Vanchuyen vc;
                foreach (object obj in pnVanchuyen.Controls) {
                    vc = (LVClient.Command.OPTObj.Vanchuyen)obj;
                    if (vc.chkOK.Checked) {
                        Cookies[citycount] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(((LVClient.Command.CityObj.City)vc.cboSource.SelectedItem).id);
                        Id[citycount] = ((LVClient.Command.CityObj.City)vc.cboSource.SelectedItem).id;
                        City[citycount] = new int[6];                  
                        City[citycount][0]=((LVClient.Command.CityObj.City)vc.cboDesc.SelectedItem).id;
                        City[citycount][1]=int.Parse("0" + vc.txtFOOD.Text);
                        City[citycount][2]=int.Parse("0" + vc.txtWOOD.Text);
                        City[citycount][3]=int.Parse("0" + vc.txtIRON.Text);
                        City[citycount][4]=int.Parse("0" + vc.txtSTONE.Text);
                        City[citycount][5]=int.Parse("0" + vc.txtMONEY.Text);
                        citycount++;
                    }
                }
            }
        }

		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				//lock (LVClient.Web.LVWeb.ispause) {
				try
				{
					Message.ForeColor = System.Drawing.Color.Red;
					SetText("Đang chạy (0%)");
					for (int i = 0; i < citycount; i++)
					{
						SetText("Đang chạy (" + (i) * 100 / citycount + "%)");
						try
						{
							Cookies[i] = LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(Id[i]);
							LVClient.Command.City.SwitchCitySlow(Id[i]);
							if (Command.Build.SelectBuilding(Id[i], 11, Cookies[i]))
							{
								Command.OPT.Vanchuyen(City[i][0],
								City[i][1],
								City[i][2],
								City[i][3],
								City[i][4],
								City[i][5], Cookies[i]);
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

				finally
				{
					Message.ForeColor = System.Drawing.Color.Blue;
				}
			}
		}
		
		public void run() 
		{
            IsRun = true;
            while (true) 
			{
				SetText("Chờ tới phiên (0%) - chờ từ lúc " + DateTime.Now.ToString("HH:mm:ss"));
				threadID = "VANCHUYEN_" + DateTime.Now.Ticks; 
				Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
				Message.ForeColor = System.Drawing.Color.Blue; 
				SetText("Đang ngủ " + Sleep/(1000*60) + " phút, chờ tí (mới chạy lúc: " + DateTime.Now.ToString("HH:mm:ss") + ")");;
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
