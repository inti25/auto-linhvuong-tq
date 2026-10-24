using System;
using System.Collections.Generic;
using System.Collections;
using System.Text;
using System.Net.Sockets;
using System.Windows.Forms;

namespace LVClient.Web {
    class ParseHeader {
        public static Hashtable Parse(string s,bool isimage) 
		{
			
			string[] arrheader = s.Split(new char[] { '\n' });
            Hashtable result = new Hashtable();

			if (s == "")
			{
				result.Add("", "");
				return result;
			}
            int i, j;
            string data = "";
            string[] arrcookie = new string[20];
            int cookiecount;
            result.Add("PROTOCOL", arrheader[0].Substring(0, arrheader[0].Length - 1));
            i = 0;
            cookiecount = 0;
            for (i = 1; i < arrheader.Length; i++) {
                if (arrheader[i] == "\r") break;
                string[] arritem = arrheader[i].Split(new char[] { ':' }, 2);
                if (arritem[0] == "Set-Cookie") {
                    arrcookie[cookiecount] = arritem[1].Substring(0, arritem[1].Length - 1);
                    cookiecount++;
                } else {
                    result.Add(arritem[0], arritem[1].Substring(0, arritem[1].Length - 1));
                }
            }
            if (cookiecount > 0) {
                result.Add("Set-Cookie", arrcookie);
            }
            for (j = i + 1; j < arrheader.Length; j++) {
                data += arrheader[j];
            }
            
            if (data.IndexOf("</html>") >= 0) {
                data = data.Substring(0, data.IndexOf("</html>") + 7);
            }else if (data.IndexOf("}") >= 0) {
                int open=0, close=0;
                for (i = 0; i < data.Length; i++) {
                    if (data[i] == '{') open++;
                    if (data[i] == '}') open--;
                    if (open == 0) {
                        data = data.Substring(0, i + 1);
                        break;
                    }
                }
            }else if (data.IndexOf("</script>") >= 0) {
                data = data.Substring(0, data.IndexOf("</script>") + 9);
            }else if (data.Length > 20) {
                if (isimage == false) {
                    throw new Exception();
                }
            }
            result.Add("DATA", data);
            return result;
        }
        public static string GetCapChaImage(string xml){
            ParseHTML parse = new ParseHTML();
            string result="";

            parse.Source = xml + "\n\r";
            while (!parse.Eof()) {
                char ch = parse.Parse();
                if (ch == 0) {
                    AttributeList tag = parse.GetTag();
                    if (tag.Name == "img") {
                        try {
                            Attribute att = (Attribute)tag.List[0];
                            if (att.Name == "id" && att.Value == "imgConfirm") {
                                att = (Attribute)tag.List[1];
                                return att.Value;
                            }
                        } catch (Exception ex) {
                        }
                    }
                }
            }

            return result;
        }
        public static Hashtable GetDataFromForm(string xml) 
		{
			
            ParseHTML parse = new ParseHTML();
            Hashtable result = new Hashtable();

            parse.Source = xml + "\n\r";
            while (!parse.Eof()) {
                char ch = parse.Parse();
                if (ch == 0) {
                    AttributeList tag = parse.GetTag();
                    if (tag.Name.ToLower() == "form") {
                        for (int i = 0; i < tag.List.Count; i++) {
                            Attribute att = (Attribute)tag.List[i];
                            if (att.Name.ToLower() == "action") {
                                result.Add("ACTION", att.Value);
                            }
                        }
                    } else if (tag.Name.ToLower() == "input") {
                        string name = "";
                        string value = "";
                        for (int i = 0; i < tag.List.Count; i++) {
                            Attribute att = (Attribute)tag.List[i];
                            if (att.Name.ToLower() == "name") {
                                name = att.Value;
                            }
                            if (att.Name.ToLower() == "value") {
                                value = att.Value;
                            }
                        }
                        result.Add(name, value);
                    }
                }
            }
            return result;
        }


		public static ArrayList GetTinTucNhacNho(string xml)
		{
			ParseHTML parse = new ParseHTML();
			//Hashtable result = new Hashtable();
			ArrayList  result = new ArrayList();

			parse.Source = xml + "\n\r";
			while (!parse.Eof())
			{
				char ch = parse.Parse();
				if (ch == 0)
				{

					AttributeList tag = parse.GetTag();
					
					if (tag.Name.ToLower() == "form")
					{
						for (int i = 0; i < tag.List.Count; i++)
						{
							Attribute att = (Attribute)tag.List[i];
							if (att.Name.ToLower() == "action")
							{
								//result.Add("ACTION", att.Value);
							}
						}
					}
					else if (tag.Name.ToLower() == "input")
					{
						string name = "";
						string value = "";
						for (int i = 0; i < tag.List.Count; i++)
						{
							Attribute att = (Attribute)tag.List[i];
							if (att.Name.ToLower() == "name")
							{
								name = att.Value;
							}
							if (att.Name.ToLower() == "value")
							{
								value = att.Value;
							}
						}
						//result.Add(name, value);
					}
				}
			}
			return result;
		}
    }
}
