using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;


namespace LVClient.LVThread
{
	public class ThreadSkeleton
	{
		delegate void SetTextCallback(string text);
		public Thread InThread;
		public string threadID;
		public bool IsRun = false;
		public Label Message;
		public int Sleep = 60000;
		public int MainProcessResult = 0;

		public ThreadSkeleton()
		{
		}
		public ThreadSkeleton(Label lbl) 
		{
            Message = lbl;
        }

		public virtual void run()
		{
			
		}

		public void Auto()
		{
			if (!IsRun)
			{
				InThread = new Thread(new ThreadStart(run));
				IsRun = true;
				InThread.Start();
			}
		}
		public void Stop()
		{
			if (IsRun)
			{
				InThread.Abort();
				InThread.Join();
				Common.ThreadManager.RemoveThread(threadID);
				Message.ForeColor = System.Drawing.Color.Blue; Message.ForeColor = System.Drawing.Color.Blue; Message.Text = "Đã dừng bởi người sử dụng";
				IsRun = false;
			}
		}
		public  void SetText(String str)
		{
            try
            {
                if (this.Message.InvokeRequired)
                {
                    SetTextCallback d = new SetTextCallback(SetText);
                    this.Message.Invoke(d, new object[] { str });
                }
                else
                {
                    this.Message.Text = str;
                }
            }
            catch (Exception ex)
            {
            }
		}
	}
}
