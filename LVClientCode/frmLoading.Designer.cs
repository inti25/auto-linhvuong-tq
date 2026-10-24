namespace LVClient
{
	partial class frmLoading
	{
		/// <summary>
		/// Required designer variable.
		/// </summary>
		private System.ComponentModel.IContainer components = null;

		/// <summary>
		/// Clean up any resources being used.
		/// </summary>
		/// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
		protected override void Dispose(bool disposing)
		{
			if (disposing && (components != null))
			{
				components.Dispose();
			}
			base.Dispose(disposing);
		}

		#region Windows Form Designer generated code

		/// <summary>
		/// Required method for Designer support - do not modify
		/// the contents of this method with the code editor.
		/// </summary>
		private void InitializeComponent()
		{
			this.lblText = new System.Windows.Forms.Label();
			this.picWait = new System.Windows.Forms.PictureBox();
			((System.ComponentModel.ISupportInitialize)(this.picWait)).BeginInit();
			this.SuspendLayout();
			// 
			// lblText
			// 
			this.lblText.AutoSize = true;
			this.lblText.Location = new System.Drawing.Point(25, 8);
			this.lblText.Name = "lblText";
			this.lblText.Size = new System.Drawing.Size(69, 13);
			this.lblText.TabIndex = 0;
			this.lblText.Text = "Loading........";
			// 
			// picWait
			// 
			this.picWait.BackColor = System.Drawing.Color.Transparent;
			this.picWait.BackgroundImageLayout = System.Windows.Forms.ImageLayout.None;
			this.picWait.Image = global::LVClient.Properties.Resources.waiting;
			this.picWait.Location = new System.Drawing.Point(6, 7);
			this.picWait.Name = "picWait";
			this.picWait.Size = new System.Drawing.Size(18, 16);
			this.picWait.TabIndex = 1;
			this.picWait.TabStop = false;
			// 
			// frmLoading
			// 
			this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
			this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
			this.BackgroundImageLayout = System.Windows.Forms.ImageLayout.None;
			this.ClientSize = new System.Drawing.Size(97, 27);
			this.ControlBox = false;
			this.Controls.Add(this.picWait);
			this.Controls.Add(this.lblText);
			this.Cursor = System.Windows.Forms.Cursors.WaitCursor;
			this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.None;
			this.MaximizeBox = false;
			this.MinimizeBox = false;
			this.Name = "frmLoading";
			this.ShowIcon = false;
			this.ShowInTaskbar = false;
			this.StartPosition = System.Windows.Forms.FormStartPosition.CenterParent;
			this.TopMost = true;
			this.Load += new System.EventHandler(this.frmLoading_Load);
			((System.ComponentModel.ISupportInitialize)(this.picWait)).EndInit();
			this.ResumeLayout(false);
			this.PerformLayout();

		}

		#endregion

		private System.Windows.Forms.Label lblText;
		private System.Windows.Forms.PictureBox picWait;
	}
}