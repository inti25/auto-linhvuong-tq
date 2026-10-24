using System;
using System.Collections.Generic;
using System.Text;		
using System.Windows.Forms;

namespace LVClient.Command.CommonObj
{
  public class MyTabPage : TabPage
  {
	  public void Enabled_()

         {

			 ((System.Windows.Forms.Control)this).Enabled = true;

         }

         public void Disable_()

         {

			 ((System.Windows.Forms.Control)this).Enabled = false;

         }

   }

}
	

