using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;
//using System.Net.Sockets;
using System.Windows.Forms;
using System.Threading;
using System.Web;
using System.Net;
using System.IO;
using System.Diagnostics;
//using LVClient.Connection.ProxySocket;
using LVClient.Connection.StarksoftProxy;
using System.Net.Sockets;


namespace LVClient.Web 
{
    public class LVWeb {

		delegate void SetTextCallback(string text);
		//delegate void SetNetworkStatusText(string text);

		//delegate void SetTextNetworkStatusCallback(string text);

        public static LoginInfo CurrentLoginInfo;
        public static string Cookies = "";
        public static LoginInfo MiscLoginInfo;
        public static Hashtable LoginFormData;
        public static int Delay = 0;
        public static int Server = 1;
        public static string LoginHtml;
        public static int SendCount = 0;
        public static string username = "";
        public static object islock= new object();
        public static object ispause= new object();
        public static bool debug = true;
        public static bool alarm = false;
        public static bool issendsms = false;
        public static bool hassend = true;
        public static int lastsmstype = -1;//1:bi danh;2:còn 30 phut;3: còn 5 phút;0:ko bi gi het;-1 moi login
        public static string smsusername = "";
        public static string smspass = "";
        public static string smsto = "";
        public static int idimage = -1;
        public static bool hacking = false;
        public static string uid;
        public static string uname;
        public static string ulgtime;
        public static string pid;
        public static string sign;
        public static string lvusername = "";
        public static string lvpassword = "";
        public static System.Windows.Forms.Timer wb;
        public static bool firstlogin = true;
        public static bool loadinput = false;
        public static bool relogin = false;
        //public static ProxySocket cursocket;
		public static Socket cursocket;
        public static string curserver;

		public static int soluonglancheckanh = 0;
		public static int soluonglancheckanhdung = 0;

		//private static frmImageCheck frImageCheck = new frmImageCheck();

		public static object isimagelock = 0;

		//public static bool imageChecking = false;

        /*private static ProxySocket ConnectSocket(string server, int port)
		{
			try
			{
				if (cursocket != null)
				{
					if (curserver == server && cursocket.Connected)
					{
						return cursocket;
					}
				}

			 	ProxySocket s = null;
				IPHostEntry hostEntry = null;

				// Get host related information.
				hostEntry = Dns.GetHostEntry(server);

				// Loop through the AddressList to obtain the supported AddressFamily. This is to avoid
				// an exception that occurs when the host IP Address is not compatible with the address family
				// (typical in the IPv6 case).
				foreach (IPAddress address in hostEntry.AddressList)
				{
					IPEndPoint ipe = new IPEndPoint(address, port);
					
					ProxySocket tempSocket =
						new ProxySocket(ipe.AddressFamily,  System.Net.Sockets.SocketType.Stream, System.Net.Sockets.ProtocolType.Tcp);

					//ProxySocket tempSocket =
					//	new ProxySocket(System.Net.Sockets.AddressFamily.InterNetwork, System.Net.Sockets.SocketType.Stream, System.Net.Sockets.ProtocolType.Tcp);
					
					// add proxy
					// set the proxy settings
					//tempSocket.ProxyEndPoint = new IPEndPoint(IPAddress.Parse("172.20.1.8"), 8080);
					//tempSocket.ProxyUser = "";
					//tempSocket.ProxyPass = "@";
					//tempSocket.ProxyType = ProxyTypes.Socks5;	// if you set this to ProxyTypes.None, 
														// the ProxySocket will act as a normal Socket

					


					tempSocket.Connect(ipe);
					while (tempSocket.Connected == false)
					{
						try
						{
							tempSocket.Connect(ipe);
							Thread.Sleep(200);
						}
						catch (Exception ex)
						{
							//Thread.Sleep(200);
						}
					}
					if (tempSocket.Connected)
					{
						s = tempSocket;

						s.SendTimeout = 1000;
						s.ReceiveTimeout = 1000;
						s.ReceiveBufferSize = 512;

						break;
					}
					else
					{
						continue;
					}
				}
				cursocket = s;
				curserver = server;
				return cursocket;
			}
			catch (Exception ex)
			{
				return null;
			}
        }
		*/

		private static Socket ConnectSocket(string server, int port)
		{
			try
			{
				if (cursocket != null)
				{
					if (curserver == server && cursocket.Connected)
					{
						return cursocket;
					}
				}

				IProxyClient proxyClient = null;
				TcpClient tcpClient = null;

				switch (LVClient.frmmain.ProxyProtocol)
				{
					case LVClient.Connection.StarksoftProxy.ProxyProtocolType.NONE:

						break;

					case LVClient.Connection.StarksoftProxy.ProxyProtocolType.HTTP:
						proxyClient = new HttpProxyClient(LVClient.frmmain.ProxyServer, Int32.Parse(LVClient.frmmain.ProxyPort));
						break;

					case LVClient.Connection.StarksoftProxy.ProxyProtocolType.SOCKS4:
						proxyClient = new Socks4ProxyClient(LVClient.frmmain.ProxyServer, Int32.Parse(LVClient.frmmain.ProxyPort));
						break;

					case LVClient.Connection.StarksoftProxy.ProxyProtocolType.SOCKS4a:
						proxyClient = new Socks4aProxyClient(LVClient.frmmain.ProxyServer, Int32.Parse(LVClient.frmmain.ProxyPort),LVClient.frmmain.ProxyUser);
						break;
					case LVClient.Connection.StarksoftProxy.ProxyProtocolType.SOCKS5:
						proxyClient = new Socks5ProxyClient(LVClient.frmmain.ProxyServer, Int32.Parse(LVClient.frmmain.ProxyPort),
																LVClient.frmmain.ProxyUser, LVClient.frmmain.ProxyPass);

						break;

				}

				try
				{
					// test to see if the user would like to connect using the proxy or connect directly 
					if (LVClient.frmmain.ProxyProtocol != LVClient.Connection.StarksoftProxy.ProxyProtocolType.NONE)
						tcpClient = proxyClient.CreateConnection(server, port);
					else
						tcpClient = new TcpClient(server, port);
				}
				catch (Exception ex)
				{
					//MessageBox.Show(ex.Message, "Connection Error");
					//return null;
					throw ex;
				}

				if (tcpClient == null) return null;


				cursocket = tcpClient.Client;
				cursocket.SendTimeout = 1000;
				cursocket.ReceiveTimeout = 1000;
				cursocket.ReceiveBufferSize = 512;

				curserver = server;
				return cursocket;
			}
			catch (Exception ex)
			{
				//return null;
				throw ex;
			}
		}

		public static Byte[] SendAndReceiveByte(string data, string host, int port, bool wait)
		{
			int count = 0;
			try
			{
				
				Socket s = null;
				while (true && count < 3)
				{
					Byte[] bytesSent = Encoding.ASCII.GetBytes(data);
					Byte[] bytesReceived = new Byte[512];
					Byte[] fullRec = new Byte[100000];
					int fullL = 0;

					// Create a socket connection with the specified server and port.

					if (s == null) s = ConnectSocket(host, port);

					if (s == null)
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}

					try
					{
						// Send request to the server.
						s.Send(bytesSent, bytesSent.Length, 0);
					}
					catch { }

					// Receive the server home page content.
					int bytes = 0;
					string page = "";

					// The following will block until te page is transmitted.
					do
					{
						try
						{
							bytes = s.Receive(bytesReceived, bytesReceived.Length, 0);
						}
						catch (Exception ex)
						{

							break;
						}
						Byte[] temp = new Byte[512];
						try
						{
							bytesReceived.CopyTo(temp, 0);
						}
						catch (Exception ex)
						{
						}
						temp.CopyTo(fullRec, fullL);
						fullL += bytes;
						page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);
						int i = page.IndexOf("Content-Length");
						if (i > -1)
						{
							i = page.IndexOf("\n", i);
						}
					}
					while (bytes > 0);

					page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);

					if (page == null || page == "")
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}

					//File.WriteAllBytes("D:/LVClient/b1",fullRec );

					Byte[] ret = new Byte[fullL];
					for (int i = 0; i < fullL; i++) ret[i] = fullRec[i];
					//File.WriteAllBytes("D:/LVClient/b2",ret );
					//GC.Collect();
					//File.WriteAllBytes(DateTime.Now.ToFileTimeUtc().ToString(), System.Text.UTF8Encoding.UTF8.GetBytes(result["DATA"].ToString()));
					s.Close();
					return ret;
				}
				return null;
			}
			catch (Exception ex)
			{
				return null;
				//throw ex;
			}

			finally
			{
				SetNetworkStatusText(count);
			}
		}
        public static Hashtable SendAndReceive(string data,string host,int port, bool wait) 
		{
			int count = 0;
			Socket s = null;
			Hashtable result = new Hashtable();
			try
			{
				while (count < 5)
				{
					Byte[] bytesSent = Encoding.ASCII.GetBytes(data);
					Byte[] bytesReceived = new Byte[512];
					Byte[] fullRec = new Byte[100000];
					int fullL = 0;

					// Create a socket connection with the specified server and port.

					if (s == null) s = ConnectSocket(host, port);

					if (s == null)
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}
					try
					{
						// Send request to the server.
						s.Send(bytesSent, bytesSent.Length, 0);
					}
					catch (Exception ex) { }

					// Receive the server home page content.
					int bytes = 0;
					string page = "";

					// The following will block until te page is transmitted.
					do
					{
						try
						{
							bytes = s.Receive(bytesReceived, bytesReceived.Length, 0);
						}
						catch (Exception ex)
						{

							break;
						}
						Byte[] temp = new Byte[512];
						try
						{
							bytesReceived.CopyTo(temp, 0);
						}
						catch (Exception ex)
						{
						}
						temp.CopyTo(fullRec, fullL);
						fullL += bytes;
						page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);
						int i = page.IndexOf("Content-Length");
						if (i > -1)
						{
							i = page.IndexOf("\n", i);
						}
					}
					while (bytes > 0);
					page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);

					//Application.DoEvents();
					if (page == "")
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}


					try
					{
						if (hacking == false)
						{
							result = ParseHeader.Parse(page, false);
						}
						else
						{
							result.Add("DATA", page);
							return result;
						}
						//chekc xem bi khoa chua
						//{"ret":1000705,"duration":66930}  bi khoa acc
						if (hacking == false)
						{
							if (result["DATA"].ToString() == "{ret:-3}")
							{
								if (idimage > -1)
								{
									idimage = -1;
									// lay lai thong tin, lai call lai loginplay, LoginPartner de lay lai cookie
									LoginEx();
									return null;
								}
								else
								{
									hacking = true;
									TestImage();
									hacking = false;
									Hashtable img = GetImage();
									string[] s1 = img["DATA"].ToString().Split(new char[] { '[', ']' });
									idimage = int.Parse(s1[2]);
									return null;
								}
							}
							// bi bat phai check anh

							if (result["DATA"].ToString() == "{ret:198599}")
							{
								idimage = -1;
								// lay lai thong tin, lai call lai loginplay, LoginPartner de lay lai cookie
								LoginEx();
								//return null;
							}


							// bi bat phai check anh

							if (result["DATA"].ToString().Contains("{\"ret\":110}") || result["DATA"].ToString().Contains("{\"ret\":110,"))
							{
								if (LVClient.frmImageCheck.imageChecking)
									LVClient.frmImageCheck.returnCheckImgValue = -1;
								else
									processCheckImage();


								//return result;

                                count++;
                                continue;
							}
							if (result["DATA"].ToString() == "<script language=\"javascript\" defer>alert('Bạn tạm thời bị cấm đăng nhập');</script>")
							{
								Thread.Sleep(30000);
								idimage = -1;
								LoginEx();
								return null;
							}


						}
					}
					catch (Exception ex)
					{
						Thread.Sleep(200);
						return null;
					}

					if (result.ContainsKey("Set-Cookie"))
					{
						Cookies = ((string[])result["Set-Cookie"])[0];
						LVClient.Web.LVWeb.CurrentLoginInfo = new LoginInfo((string[])result["Set-Cookie"]);
					}
					//GC.Collect();
					//File.WriteAllBytes(DateTime.Now.ToFileTimeUtc().ToString(), System.Text.UTF8Encoding.UTF8.GetBytes(result["DATA"].ToString()));
					s.Close();
					return result;
                }  // end while (true && count < 3)
				return result;
			}
			catch (Exception ex)
			{
				return null;
			}
			finally
			{
				SetNetworkStatusText(count);
			}
        }



		private  static void SetNetworkStatusText(int count)
		{
			//SetStatusText((100-count*10) +  "%");
		}

		private static void SetStatusText(String str)
		{
			if (frmmain.LVFRMMAIN.lblNetworkStatus.InvokeRequired)
			{
				SetTextCallback d = new SetTextCallback(SetStatusText);
				frmmain.LVFRMMAIN.lblNetworkStatus.Invoke(d, new object[] { str });
			}
			else
			{
				frmmain.LVFRMMAIN.lblNetworkStatus.Text = str;
			}
		}

        public static Hashtable SendAndReceive2(string data, string host, int port, bool wait) {
			int count = 0;
			Socket s = null;
			Hashtable result = null;
			try
			{
				while (true && count < 3)
				{
					Byte[] bytesSent = Encoding.ASCII.GetBytes(data);
					Byte[] bytesReceived = new Byte[512];
					Byte[] fullRec = new Byte[100000];
					int fullL = 0;

					// Create a socket connection with the specified server and port.
					if (s == null) s = ConnectSocket(host, port);

					if (s == null)
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}

					
					// Send request to the server.
					s.Send(bytesSent, bytesSent.Length, 0);
					// Receive the server home page content.
					int bytes = 0;
					string page = "";

					// The following will block until te page is transmitted.
					do
					{
						try
						{
							bytes = s.Receive(bytesReceived, bytesReceived.Length, 0);
						}
						catch (Exception ex)
						{
							break;
						}
						Byte[] temp = new Byte[512];
						try
						{
							bytesReceived.CopyTo(temp, 0);
						}
						catch (Exception ex)
						{
						}
						temp.CopyTo(fullRec, fullL);
						fullL += bytes;

					}
					while (bytes > 0);


					page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);
					if (page == "")
					{
						count++;
						Thread.Sleep(1000);
						continue;
					}


					result = ParseHeader.Parse(page, false);
					if (result.ContainsKey("Set-Cookie"))
					{
						Cookies = ((string[])result["Set-Cookie"])[0];
						LVClient.Web.LVWeb.CurrentLoginInfo = new LoginInfo((string[])result["Set-Cookie"]);
					}
					//GC.Collect();
					//File.WriteAllBytes(DateTime.Now.ToFileTimeUtc().ToString(), System.Text.UTF8Encoding.UTF8.GetBytes(result["DATA"].ToString()));
					s.Close();
					return result;

				}
				return result;
			}
			catch (Exception ex)
			{
				return null;
			}
			finally
			{
				SetNetworkStatusText(count);
			}
        }
        public static Hashtable SendAndReceiveMobi(string data, string host, int port, bool wait) {
            while (true) {
                Byte[] bytesSent = Encoding.ASCII.GetBytes(data);
                Byte[] bytesReceived = new Byte[512];
                Byte[] fullRec = new Byte[100000];
                int fullL = 0;

                // Create a socket connection with the specified server and port.
				Socket s = ConnectSocket(host, port);

                if (s == null)
                    return null;

                // Send request to the server.
                s.Send(bytesSent, bytesSent.Length, 0);
                // Receive the server home page content.
                int bytes = 0;
                string page = "";

                // The following will block until te page is transmitted.
                do {
                    try {
                        bytes = s.Receive(bytesReceived, bytesReceived.Length, 0);
                    } catch (Exception ex) {
                        break;
                    }
                    Byte[] temp = new Byte[512];
                    try {
                        bytesReceived.CopyTo(temp, 0);
                    } catch (Exception ex) {
                    }
                    temp.CopyTo(fullRec, fullL);
                    fullL += bytes;

                }
                while (bytes > 0);
                page = System.Text.Encoding.UTF8.GetString(fullRec, 0, fullL);
                Hashtable result = null;
                try {
                    result = ParseHeader.Parse(page,false);
                } catch {
                    continue;
                }

                if (result.ContainsKey("Set-Cookie")) {
                    //Cookies = ((string[])result["Set-Cookie"])[0];
                    //LVClient.Web.LVWeb.CurrentLoginInfo = new LoginInfo((string[])result["Set-Cookie"]);
                }
                //GC.Collect();
                //File.WriteAllBytes(DateTime.Now.ToFileTimeUtc().ToString(), System.Text.UTF8Encoding.UTF8.GetBytes(result["DATA"].ToString()));
                return result;
            }
        }
        public static Byte[] GetImage(string data,string host,int port) {
            System.Net.Sockets.TcpClient client = new System.Net.Sockets.TcpClient(host, port);
            client.SendTimeout = 5000;
            client.ReceiveTimeout = 5000;
            Byte[] bytedata = System.Text.Encoding.ASCII.GetBytes(data);
            Byte[] result  = new Byte[0];
            int beginread = 0;
            int j=0;
            client.GetStream().Write(bytedata, 0, bytedata.Length);
            //Thread.Sleep(2000);
            bytedata = new Byte[100000];
            Int32 bytes = client.GetStream().Read(bytedata, 0, bytedata.Length);
            for (int i = 0; i < bytes; i++) {
                if (bytedata[i] == 13 && bytedata[i + 1] == 10 && bytedata[i + 2] == 13 && bytedata[i + 3] == 10) {
                    beginread = i + 4;
                    result = new Byte[bytes-(i+3)];
                    break;
                }
            }
            for (int i = beginread; i < bytes; i++) {
                result[j] = bytedata[i];
                j++;
            }
            return result;
        }

        public static Hashtable LoginForm() {
            string header = "GET http://login.linhvuong.zooz.vn/login.aspx?server=" + Server + " HTTP/1.1\n";
            header += "Host: login.linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            //header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 0\n";
            header += "Proxy-Connection: close\n";
            header += "Referer: http://linhvuong.zooz.vn/news/\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "\n";
            
            return SendAndReceive2(header, "login.linhvuong.zooz.vn", 80, true);
        }
        public static Hashtable TestImage() 
		{
            Random rnd = new Random();
            string header = "GET http://s"+Server+".linhvuong.zooz.vn/VerifyCode.gif?t=8599&xf="+rnd.NextDouble()+" HTTP/1.1\n";

			//string header = "GET http://s" + Server + ".linhvuong.zooz.vn/VerifyCode.gif?t=8599&xf=0.19394869838400008 HTTP/1.1\n";

            header += "Host: s"+Server+ ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
            //header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
			header += "Accept: image/png,image/*;q=0.8,*/*;q=0.5\n";
			header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";      
            header += "Referer: http://s" + Server + ".linhvuong.zooz.vn/city\n";
            header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "\n";
            return SendAndReceive(header, "s" + Server + ".linhvuong.zooz.vn", 80, true);
        }
		public static Byte[] TestImage_()
		{
			Random rnd = new Random();
			string header = "GET http://s" + Server + ".linhvuong.zooz.vn/VerifyCode.gif?t=8599&xf=" + rnd.NextDouble() + " HTTP/1.1\n";

			//string header = "GET http://s" + Server + ".linhvuong.zooz.vn/VerifyCode.gif?t=8599&xf=0.19394869838400008 HTTP/1.1\n";

			header += "Host: s" + Server + ".linhvuong.zooz.vn\n";
			header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
			//header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
			header += "Accept: image/png,image/*;q=0.8,*/*;q=0.5\n";
			header += "Accept-Language: en-us,en;q=0.5\n";
			//header += "Accept-Encoding: gzip,deflate\n";
			header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
			header += "Keep-Alive: 300\n";
			header += "Referer: http://s" + Server + ".linhvuong.zooz.vn/city\n";
			header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
			header += "Content-Type: application/x-www-form-urlencoded\n";
			header += "\n";
			return SendAndReceiveByte(header, "s" + Server + ".linhvuong.zooz.vn", 80, true);
		}
        public static Hashtable GetImage() 
		{
            string data = "";
            string header = "POST http://s"+Server+".linhvuong.zooz.vn/GateWay/Common.ashx?id=73&0.017088377954387002 HTTP/1.1\n";
            header += "Host: s" + Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            //header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Proxy-Connection: keep-alive\n";
			header += "X-Requested-With: XMLHttpRequest\n";
			header += "X-Prototype-Version: 1.5.0\n";
            header += "Referer: http://s" + Server + ".linhvuong.zooz.vn/city\n";
			header += "Pragma: no-cache\n";
			header += "Cache-Control: no-cache\n";
            header += "Cookie: " + Web.LVWeb.CurrentLoginInfo.MakeCookiesString() + "\n";
            header += "Content-Type: application/x-www-form-urlencoded; charset=UTF-8\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
																
            return SendAndReceive(header + data, "s" + Server + ".linhvuong.zooz.vn", 80, true);
        }
        public static Byte[] CapchaImage(string src) 
		{
            string header = "GET "+src+" HTTP/1.1\n";
            header += "Host: login.linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            //header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Proxy-Connection: keep-alive\n";
            header += "Referer: " + src + "\n";
            header += "Cookie: "+Cookies+"\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "\n";

            return GetImage(header, "login.linhvuong.zooz.vn", 80);
        }

		public static void processCheckImage() 
		{
            
			// dang check, thoat luon
			if (LVClient.frmImageCheck.imageChecking) return;

			if (LVClient.frmmain._tuxacnhananh == 0) return;		// ko lam gi, thoat luon
			
			
			lock (isimagelock)
			{
				int repeatcount = 0;
				while (repeatcount < 10)
				{
					try
					{
						LVClient.frmImageCheck.imageChecking = true;
						idimage = -1;

						hacking = true;
						int count = 0;
						Byte[] imgRight = null; ;
						do
						{
							imgRight = TestImage_();
							count++;
						} while (imgRight == null && count < 10);

						hacking = false;

						//Lay 4 anh con
						Hashtable img = GetImage();
						string[] s1 = img["DATA"].ToString().Split(new char[] { '[', ']' });

						LVClient.frmImageCheck.imgChoseID[0] = int.Parse(s1[2]);
						LVClient.frmImageCheck.imgChoseID[1] = int.Parse(s1[4]);
						LVClient.frmImageCheck.imgChoseID[2] = int.Parse(s1[6]);
						LVClient.frmImageCheck.imgChoseID[3] = int.Parse(s1[8]);

						/*
						//for test only
						string ssData = Encoding.ASCII.GetString(imgRight);
						int iidex = ssData.IndexOf("\r\n\r\n");
						iidex = iidex + 4;
						Byte[] scontent = new Byte[imgRight.Length - iidex];


						//laay noi dung anh
						for (int i = iidex; i < imgRight.Length; i++)
						{
							scontent[i - iidex] = imgRight[i];
						}
						File.WriteAllBytes("D:/LVClient/VerifyGif.gif", scontent);
						
						string simgPath = "http://3gmap1.linhvuong.zooz.vn/Statics/Images/history/";
						string ss1 = (simgPath + LVClient.frmImageCheck.imgChoseID[0] + ".gif");
						string ss2 = (simgPath + LVClient.frmImageCheck.imgChoseID[1] + ".gif");
						string ss3 = (simgPath + LVClient.frmImageCheck.imgChoseID[2] + ".gif");
						string ss4 = (simgPath + LVClient.frmImageCheck.imgChoseID[3] + ".gif");
						//------------------------
						*/

						
													
						if (LVClient.frmmain._tuxacnhananh == 2)		// tu xac nhan anh	
						{
							int MaxCheckSai = int.Parse( LVClient.frmmain.LVFRMMAIN.txtXacNhanAnhMaxCheck.Text);
							if (LVClient.frmmain.LVFRMMAIN.SoLanTuCheckAnhSaiLienTiep >= MaxCheckSai)
							{
								int duration = int.Parse(LVClient.frmmain.LVFRMMAIN.txtXacNhanAnhMinTimeCheck.Text);

								string str = "Last check: " + LVClient.frmmain.LVFRMMAIN.LastTimeImageCheck.ToString("HH:mm:ss") + ". Dừng check vì sai quá " + MaxCheckSai + " lần.";
								str += " Check tiếp sau " + LVClient.frmmain.LVFRMMAIN.LastTimeImageCheck.Add(new System.TimeSpan(duration, 0, 0)).ToString("HH:mm:ss");
								SetCountText(str);


								if (DateTime.Compare(LVClient.frmmain.LVFRMMAIN.LastTimeImageCheck.Add(new System.TimeSpan(duration, 0, 0)), DateTime.Now) <= 0)
								{
									LVClient.frmmain.LVFRMMAIN.SoLanTuCheckAnhSaiLienTiep--;
								}
								else
								{
									break;

								}
							}

							try
							{
								if (LVClient.frmmain._chuongbao)
								{
									System.Media.SoundPlayer mp = new System.Media.SoundPlayer();
									mp.SoundLocation = @"alert.wav";
									mp.Play();

								}
							}
							catch (Exception ex) { }

							int imgidselect = (new Random()).Next(4);
							string retCode = sendChoiceImageCheck(LVClient.frmImageCheck.imgChoseID[imgidselect]);
							LVClient.frmImageCheck.imageChecking = false;
							LVClient.frmmain.LVFRMMAIN.LastTimeImageCheck = DateTime.Now;

							soluonglancheckanh++;
							string strCheck = "false";
							if (retCode == "0")
							{
								LVClient.frmmain.LVFRMMAIN.SoLanTuCheckAnhSaiLienTiep = 0;
								soluonglancheckanhdung++;
								strCheck = "ok";
							}
							else
							{
								LVClient.frmmain.LVFRMMAIN.SoLanTuCheckAnhSaiLienTiep++; 
							}
				
							SetCountText("(" + soluonglancheckanhdung + "/" + soluonglancheckanh + " - "
												+ soluonglancheckanhdung * 100 / soluonglancheckanh + "%), last check: " + DateTime.Now.ToString("HH:mm:ss") + " - " + strCheck);

							
							break;
						}
						else                 // hien anh de check
						{
							string sData = Encoding.ASCII.GetString(imgRight);
							int idex = sData.IndexOf("\r\n\r\n");
							idex = idex + 4;
							Byte[] content = new Byte[imgRight.Length - idex];

							//imgRight.CopyTo(content, idex);

							System.Array.Copy(imgRight, idex, content, 0, imgRight.Length - idex);

							//laay noi dung anh
							/*
							for (int i = idex; i < imgRight.Length; i++)
							{
								content[i - idex] = imgRight[i];
							}
							 */ 
							 
							//File.WriteAllBytes("D:/LVClient/VerifyGif.gif", content);
							
							frmImageCheck frImageCheck = new frmImageCheck();
							System.IO.Stream bs = new System.IO.MemoryStream();
							bs.Write(content, 0, content.Length);

							frImageCheck.picSamplePic.WaitOnLoad = true;
							frImageCheck.picSamplePic.Image = System.Drawing.Image.FromStream(bs);

							//frImageCheck.picSamplePic.Image = System.Drawing.Image.FromFile("D:/LVClient/VerifyGif.gif");	

							string imgPath = "http://3gmap1.linhvuong.zooz.vn/Statics/Images/history/";

							try
							{
								if (LVClient.frmmain._chuongbao)
								{
									System.Media.SoundPlayer mp = new System.Media.SoundPlayer();
									mp.SoundLocation = @"alert.wav";
									mp.Play();

								}
							}
							catch (Exception ex) { }

							/*
							 * frImageCheck.pic1.ImageLocation = imgPath + frImageCheck.imgChoseID[0] + ".gif";
							frImageCheck.pic2.ImageLocation = imgPath + frImageCheck.imgChoseID[1] + ".gif";
							frImageCheck.pic3.ImageLocation = imgPath + frImageCheck.imgChoseID[2] + ".gif";
							frImageCheck.pic4.ImageLocation = imgPath + frImageCheck.imgChoseID[3] + ".gif";
						   */
							frImageCheck.pic1.WaitOnLoad = false;
							frImageCheck.pic2.WaitOnLoad = false;
							frImageCheck.pic3.WaitOnLoad = false;
							frImageCheck.pic4.WaitOnLoad = false;

							frImageCheck.pic1.LoadAsync(imgPath + LVClient.frmImageCheck.imgChoseID[0] + ".gif");
							frImageCheck.pic2.LoadAsync(imgPath + LVClient.frmImageCheck.imgChoseID[1] + ".gif");
							frImageCheck.pic3.LoadAsync(imgPath + LVClient.frmImageCheck.imgChoseID[2] + ".gif");
							frImageCheck.pic4.LoadAsync(imgPath + LVClient.frmImageCheck.imgChoseID[3] + ".gif");

							//frImageCheck.picSamplePic.
							//frImageCheck.picSamplePic.Show();
							//frImageCheck.Visible = true;



							// hien form de user check anh
							frImageCheck.Activate();
							frImageCheck.ShowDialog();
							//frImageCheck.Refresh();
							string retCode="";
							if (LVClient.frmmain.imagecheckid != -1)
							{
								retCode = LVClient.Web.LVWeb.sendChoiceImageCheck(LVClient.frmmain.imagecheckid);

								string strCheck = "false";
								if (retCode == "0")
								{
									strCheck = "ok";
								}
								double percent = 0;
								if (soluonglancheckanh != 0)
								{
									percent = soluonglancheckanhdung * 100 / soluonglancheckanh;
								}

								SetCountText("(" + soluonglancheckanhdung + "/" + soluonglancheckanh + " - "
													+ percent + "%), last check: " + DateTime.Now.ToString("HH:mm:ss") + " - " + strCheck);

								LVClient.frmmain.LVFRMMAIN.SoLanTuCheckAnhSaiLienTiep = 0;
							}

							LVClient.frmImageCheck.imageChecking = false;

							

							
							
							break;		// while count <10

						}
					
					}
					catch (Exception ex)
					{
						LVClient.frmImageCheck.imageChecking = false;
						repeatcount++;
					}
				} //				while (repeatcount < 10)

				LVClient.frmImageCheck.imageChecking = false;
			 }


		}

		private static void SetCountText(String str)
		{
			if (frmmain.LVFRMMAIN.lblfrmSolancheckAnh.InvokeRequired)
			{
				SetTextCallback d = new SetTextCallback(SetCountText);
				frmmain.LVFRMMAIN.lblfrmSolancheckAnh.Invoke(d, new object[] { str });
			}
			else
			{
				frmmain.LVFRMMAIN.lblfrmSolancheckAnh.Text = str;
			}
		}
		public static string sendChoiceImageCheck(int imgid)
		{
			//string data = parameter + "&num=" + LVClient.Web.LVWeb.idimage;

			try
			{
				LVClient.Web.LVWeb.idimage = imgid;
				int count = 0;
				Hashtable battle = null;
				do
				{
					battle = LVClient.Command.OPT.Execute(102, "", true);
					count++;
				} while (battle == null && count < 5);

				string retCode = battle["ret"].ToString();


				//{"ret":1000705,"duration":66930}  bi khoa acc

				//LVClient.frmImageCheck.returnCheckImgValue = 0; 
				switch (retCode)
				{
					case "0":						// ok, chon dung hinh
						//this.Close();
						LVClient.frmImageCheck.returnCheckImgValue = 0;
						break;

					case "110":						// Chon sai hinh
						LVClient.frmImageCheck.returnCheckImgValue = -1;
						//this.Close();
						break;

					default:

						if (retCode.Substring(0, 4) == "1000")
							//Thread.Sleep((int.Parse(retCode) - 1000000) * 1000);


							//int intCode = int.Parse(retCode);
							LVClient.frmImageCheck.returnCheckImgValue = int.Parse(retCode);
						break;


					/*
									case "1000300":					// Chon sai hinh
										//this.Close();
										//LVClient.Web.LVWeb.imageChecking = false;
										//LVClient.Web.LVWeb.processCheckImage();
										LVClient.frmImageCheck.returnCheckImgValue = int.Parse(retCode);
										break;
									case "1000600":						// Bi khoa do chon sai hinh
										//this.Close();
										LVClient.frmImageCheck.returnCheckImgValue = int.Parse(retCode);

										break;
									case "1000900":
										LVClient.frmImageCheck.returnCheckImgValue = int.Parse(retCode);

										//this.Close();
										break;
					*/
				}

				//LVClient.frmImageCheck.imageChecking = false;
				//this.Close();
				return retCode;
			}
			catch (Exception ex)
			{
				return "";
			}
		}
		
        public static Hashtable Login() {
            string data = "";
            foreach (object key in LoginFormData.Keys) {
                string ikey = key.ToString();
                data += ikey + "=" + HttpUtility.UrlEncode(LoginFormData[ikey].ToString()) + "&";
            }
            string header = "POST http://login.linhvuong.zooz.vn/login.aspx?server=" + Server + " HTTP/1.1\n";
            header += "Host: login.linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727)\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
           // header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 300\n";
            header += "Proxy-Connection: keep-alive\n";
            header += "Referer: http://login.linhvuong.zooz.vn/login.aspx?server=" + Server + "\n";
            header += "Cookie: " + Cookies + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            return SendAndReceive2(header + data, "login.linhvuong.zooz.vn", 80,true);
        }
        public static Hashtable LoginPlay() {
            string data = "";
            string header = "POST http://login.linhvuong.zooz.vn/play.aspx?server=" + Server + " HTTP/1.1\n";
            header += "Host: s1.linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            //header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 0\n";
            header += "Proxy-Connection: close\n";
            header += "Referer: http://login.linhvuong.zooz.vn/play.aspx?server=" + Server + "\n";
            header += "Cookie: " + Cookies + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            return SendAndReceive2(header + data, "login.linhvuong.zooz.vn", 80, true);
        }
        public static Hashtable LoginPartner(string uid, string uname, string ulgtime, string pid, string sign) {
            string data = "uid=" + uid + "&uname=" + uname + "&ulgtime=" + ulgtime + "&pid=" + pid + "&sign=" + sign + "";
            string header = "POST http://s" + Server + ".linhvuong.zooz.vn/Interfaces/login_partner.aspx HTTP/1.1\n";
            header += "Host: s" + Server + ".linhvuong.zooz.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*//*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            //header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
			header += "Keep-Alive: 300\n";
			header += "Connection: keep-alive\n";
			//header += "Keep-Alive: 0\n";
            //header += "Connection: close\n";
            //header += "Proxy-Connection: close\n";
            header += "Referer: http://s" + Server + ".linhvuong.zooz.vn/Interfaces/login_partner.aspx\n";
            header += "Cookie: sg_cur_uid_1=14928; __utma=177481006.3759498242394892300.1231373307.1231373307.1231373307.1; __utmz=177481006.1231373307.1.1.utmcsr=linhvuong.zooz.vn|utmccn=(referral)|utmcmd=referral|utmcct=/news/66/134/index.htm; __utma=70309261.407652934.1231393052.1232469523.1232512924.52; __utmz=70309261.1231821835.20.2.utmcsr=diendan.vtc.vn|utmccn=(referral)|utmcmd=referral|utmcct=/tan_cong_thanh_qua_6_lan/m_4477486/tm.htm; __utmb=70309261.1.10.1232512924; __utmc=70309261\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            return SendAndReceive2(header + data, "s" + Server + ".linhvuong.zooz.vn", 80, true);
            
            
            /*
            HttpWebRequest h = (HttpWebRequest)WebRequest.Create("http://s" + Server + ".linhvuong.zooz.vn/Interfaces/login_partner.aspx"); ;
            //h.Headers["Host"] = "s1.linhvuong.zooz.vn";
            h.UserAgent = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5";
            h.Accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*//*;q=0.8";
            h.Headers["Accept-Language"] = "en-us,en;q=0.5";
            h.Headers["Accept-Encoding"] = "gzip,deflate";
            h.Headers["Accept-Charset"] = "ISO-8859-1,utf-8;q=0.7,*;q=0.7";
            h.KeepAlive = false;
            //h.Proxy.Cr
            h.Referer = "http://s" + Server + ".linhvuong.zooz.vn/Interfaces/login_partner.aspx";
            h.Headers["Cookie"] = "sg_cur_uid_1=14928; __utma=177481006.3759498242394892300.1231373307.1231373307.1231373307.1; __utmz=177481006.1231373307.1.1.utmcsr=linhvuong.zooz.vn|utmccn=(referral)|utmcmd=referral|utmcct=/news/66/134/index.htm; __utma=70309261.407652934.1231393052.1232469523.1232512924.52; __utmz=70309261.1231821835.20.2.utmcsr=diendan.vtc.vn|utmccn=(referral)|utmcmd=referral|utmcct=/tan_cong_thanh_qua_6_lan/m_4477486/tm.htm; __utmb=70309261.1.10.1232512924; __utmc=70309261";
            h.ContentType = "application/x-www-form-urlencoded";
            h.ContentLength = data.Length;
            h.Method = "POST";
            h.ProtocolVersion = new System.Version("1.1");
            StreamWriter stream = new StreamWriter
            (h.GetRequestStream(),Encoding.ASCII);
            stream.Write(data);
            stream.Flush();
            stream.Close();
            WebResponse lgResponse = h.GetResponse();
            StreamReader reader = new StreamReader(lgResponse.GetResponseStream());
            string s = reader.ReadToEnd();
            s = "";
            return null;
            */
        }
        public static Hashtable LoginMobi(string username, string password, string to, string message) {
            string data = "username=" + username + "&password="+password;
            string header = "POST http://www.mobifone.com.vn/web/vn/users/authenticate.jsp HTTP/1.1\n";
            header += "Host: www.mobifone.com.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 0\n";
            header += "Proxy-Connection: close\n";
            header += "Referer: http://www.mobifone.com.vn/web/vn/users/authenticate.jsp\n";
            //header += "Cookie: " + Cookies + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            Hashtable temp = SendAndReceiveMobi(header + data, "www.mobifone.com.vn", 80, true);
            data = "phonenum="+to+"&message=" + message + "&advFlg=OFF&chargeFlg=0&CCode=84&smsTplId=&mSelect=&pbList=";
            header = "POST http://www.mobifone.com.vn/web/vn/sms/result.jsp HTTP/1.1\n";
            header += "Host: www.mobifone.com.vn\n";
            header += "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.5) Gecko/2008120122 Firefox/3.0.5\n";
            header += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\n";
            header += "Accept-Language: en-us,en;q=0.5\n";
            header += "Accept-Encoding: gzip,deflate\n";
            header += "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n";
            header += "Keep-Alive: 0\n";
            header += "Proxy-Connection: close\n";
            header += "Referer: http://www.mobifone.com.vn/web/vn/sms/index.jsp\n";
            header += "Cookie: " + ((string[])temp["Set-Cookie"])[0] + "\n";
            header += "Content-Type: application/x-www-form-urlencoded\n";
            header += "Content-Length: " + (data.Length) + "\n";
            header += "\n";
            temp = SendAndReceiveMobi(header + data, "www.mobifone.com.vn", 80, true);

            return null;
            
        }
        public static void LoginEx() {
            Hashtable loginform = LVClient.Web.LVWeb.LoginForm();
            //ChallengeScript":"eval(\u0027835+409\u0027)
            //calculate antibot
            string data = loginform["DATA"].ToString();
            int i = data.IndexOf("\\u0027");
            int j = data.IndexOf("\\u0027", i + 1);
            string[] oper = data.Substring(i + 6, (j - i) - 6).Split(new char[] { '+' });
            int antibot = int.Parse(oper[0].Trim()) + int.Parse(oper[1].Trim());
            Hashtable logindata = Web.ParseHeader.GetDataFromForm(data);
            logindata["NoBot1$NoBot1_NoBotExtender_ClientState"] = antibot.ToString();
            logindata["TxtPass"] = lvpassword;
            logindata["TxtUserName"] = lvusername;
            logindata.Remove("imgLoginLogOut");
            logindata["imgLoginLogOut.x"] = 10;
            logindata["imgLoginLogOut.y"] = 10;
            LVClient.Web.LVWeb.LoginFormData = logindata;
            Hashtable temp = LVClient.Web.LVWeb.Login();
            temp = LVClient.Web.LVWeb.LoginPlay();
            LVClient.Web.LVWeb.LoginHtml = temp["DATA"].ToString();
            Hashtable lastlogindata = Web.ParseHeader.GetDataFromForm(LVClient.Web.LVWeb.LoginHtml);
            Hashtable lastlogin = Web.LVWeb.LoginPartner(lastlogindata["uid"].ToString(), lastlogindata["uname"].ToString(), lastlogindata["ulgtime"].ToString(), lastlogindata["pid"].ToString(), lastlogindata["sign"].ToString());
            Web.LVWeb.CurrentLoginInfo = new Web.LoginInfo((string[])lastlogin["Set-Cookie"]);
                                
         
        }
    }
}
