using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread {
    class BANTHUONG {
        public Thread InThread; public string threadID;
        public bool IsRun = false;
		public bool ShowMessage = false;
		public BANTHUONG(bool showmessage) 
		{
			this.ShowMessage = showmessage;
        }
        public void GetParameter()
		{
        }

		/*
		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
				try
				{
					string ok = "";
					string fail = "";
					Hashtable g = null;
					int count = 0;
					foreach (LVClient.Command.CityObj.City cty in LVClient.Command.CityObj.City.AllCity)
					{

						LVClient.Command.City.SwitchCitySlow(cty.id);
						count = 0;
						do
						{
							g = LVClient.Command.Common.GetAllGeneral();
							count++;
						} while (g == null && count < 5);
						if (g == null) continue;
						ArrayList item = (ArrayList)g["generals"];
						for (int i = 0; i < item.Count; i++)
						{
							ArrayList oneg = (ArrayList)item[i];
							if (int.Parse(oneg[7].ToString()) != 100)
							{
								try
								{

									if (LVClient.Command.OPT.BanThuong(cty.id, int.Parse(oneg[0].ToString()), int.Parse(oneg[6].ToString()) * 10 * (100 - int.Parse(oneg[7].ToString())), LVClient.Web.LVWeb.CurrentLoginInfo.MakeCookiesString(cty.id)))
									{
										ok += oneg[1].ToString() + ", ";
									}
									else
									{
										fail += oneg[1].ToString() + ", ";
									}
								}
								catch (Exception ex)
								{
									fail += oneg[1].ToString() + ", ";
								}
							}
						}
					}
					if (ShowMessage) MessageBox.Show("Đã ban thưởng thành công cho: " + (ok == "" ? "Chả ai được ban thưởng" : ok) + "\r\n"
						+ "Mấy ông sau đây không chịu nhận: " + (fail == "" ? "Chả có ông nào không lấy" : fail), LVClient.Web.LVWeb.lvusername + " ban thưởng" );
				}
				catch (Exception ex)
				{

				}
				finally
				{
					Common.ThreadManager.RemoveThread(threadID);
				}
			}
		}
		*/
		private void mainprocess()
		{
			//lock (LVClient.Web.LVWeb.islock)
			{
                try
                {
                    string ok = "";
                    string fail = "";
                    LVClient.Command.OPT.BanThuongAll(ref ok, ref fail);
                    if (ShowMessage) MessageBox.Show("Đã ban thưởng thành công cho: " + (ok == "" ? "Chả ai được ban thưởng" : ok) + "\r\n"
                        + "Mấy ông sau đây không chịu nhận: " + (fail == "" ? "Chả có ông nào không lấy" : fail), LVClient.Web.LVWeb.lvusername + " ban thưởng");
                }
                catch (Exception ex)
                {

                }
                finally
                {
                    try
                    {
                        Common.ThreadManager.RemoveThread(threadID);
                    }
                    catch (Exception ex) { }
                }
			}
		}
        public void run() 
		{
            IsRun = true;
			threadID = "BANTHUONG_" + DateTime.Now.Ticks;
			Common.ThreadManager.TakeResourceAndRun(threadID, mainprocess);
			Common.ThreadManager.RemoveThread(threadID);
			IsRun = false;
           
        }
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
            if (IsRun) {
                InThread.Abort();
                InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
                IsRun = false;
            }
        }
    }
}
