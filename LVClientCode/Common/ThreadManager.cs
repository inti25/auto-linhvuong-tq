using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Threading;


namespace LVClient.Common
{
	public class ThreadManager
	{

		public static ArrayList s_alRegister = new ArrayList();
		public static ArrayList s_funcRunning = new ArrayList();

		public static object s_objResource = new object();

		public static void RemoveThread(string strThreadId)
		{
			lock (s_alRegister)
			{			 
				s_alRegister.Remove(strThreadId);	
			} 
		}

		public static void TakeResourceAndRun(string strThreadId, ThreadStart func)
		{

			string tempid;
			lock (s_alRegister)
			{


				// Kiểm tra xem ID này đã có trong list chưa
				for (int i = 0; i < s_alRegister.Count; i++)
				{
					tempid = s_alRegister[i].ToString();
					if (strThreadId.Substring(0, strThreadId.IndexOf("_")) == tempid.Substring(0, tempid.IndexOf("_")))
					{
						return;	// thoát ra nếu đã có trong list
					}
				}

				s_alRegister.Add(strThreadId);
			}

			while (true)
			{
				lock (s_objResource)
				{


                    /*
                    //Kieemtra xem co thang nao chay qua 1 tieng chua
                    if (s_funcRunning.Count > 0)
                    {
                        tempid = s_funcRunning[0].ToString();
                        //tempid = tempid.Substring(0, tempid.IndexOf("_", tempid.IndexOf("_", 0) + 1));
                        tempid = tempid.Substring(tempid.IndexOf("_", tempid.IndexOf("_", 0) + 1) + 1);
                        string h = tempid.Substring(0, tempid.IndexOf(":"));
                        tempid = tempid.Substring(h.Length + 1);
                        string m = tempid.Substring(0, tempid.IndexOf(":"));
                        tempid = tempid.Substring(m.Length + 1);
                        string s = tempid;


                        DateTime x = new DateTime(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day,
                                        int.Parse(h), int.Parse(m), int.Parse(s));

                        System.TimeSpan k = DateTime.Now - x;

                        //if(Math.Abs(k.Hours * 60)  > 1
                    }
                    */

  
                  
                    while (true)
                    {
                        if (s_funcRunning.Count <= 0) break;

                        if (s_alRegister.Count == 0)
                        {
                            s_funcRunning.Clear();
                            s_alRegister.Add(strThreadId);

                            break;
                        }
                        
                        tempid = s_funcRunning[0].ToString();
                        tempid = tempid.Substring(0, tempid.IndexOf("_", tempid.IndexOf("_", 0) + 1));
                        if (s_alRegister[0].ToString() != tempid)
                            s_alRegister.RemoveAt(0);
                        else
                            break;
                    }
                     

                    if (s_alRegister.Count == 0) s_alRegister.Add(strThreadId);
                    

					if (s_alRegister != null && s_alRegister.Count >0 &&  string.Equals((string)s_alRegister[0], strThreadId))
					{
						try
						{
							if (s_funcRunning.Count > 0) s_funcRunning.Clear();
							s_funcRunning.Add(strThreadId + "_" + DateTime.Now.ToString("HH:mm:ss"));
							
							func();

						}
						catch (Exception ex)
						{
						}

                        
                        
                            
                        s_funcRunning.RemoveAt(0);
                        s_alRegister.RemoveAt(0);

                        break;
					}	// end if (s_alRegister != null && s_alRegister.Count >0 &&  string.Equals((string)s_alRegister[0], strThreadId))
				} // end lock (s_objResource)

				System.Threading.Thread.Sleep(10);				
			}  // end while (true)
		}
	}


}
