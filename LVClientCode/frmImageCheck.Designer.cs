namespace LVClient
{
	partial class frmImageCheck
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
			this.components = new System.ComponentModel.Container();
			System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(frmImageCheck));
			this.pic4 = new System.Windows.Forms.PictureBox();
			this.pic3 = new System.Windows.Forms.PictureBox();
			this.pic2 = new System.Windows.Forms.PictureBox();
			this.pic1 = new System.Windows.Forms.PictureBox();
			this.picSamplePic = new System.Windows.Forms.PictureBox();
			this.timer1 = new System.Windows.Forms.Timer(this.components);
			((System.ComponentModel.ISupportInitialize)(this.pic4)).BeginInit();
			((System.ComponentModel.ISupportInitialize)(this.pic3)).BeginInit();
			((System.ComponentModel.ISupportInitialize)(this.pic2)).BeginInit();
			((System.ComponentModel.ISupportInitialize)(this.pic1)).BeginInit();
			((System.ComponentModel.ISupportInitialize)(this.picSamplePic)).BeginInit();
			this.SuspendLayout();
			// 
			// pic4
			// 
			this.pic4.Cursor = System.Windows.Forms.Cursors.Hand;
			this.pic4.Image = ((System.Drawing.Image)(resources.GetObject("pic4.Image")));
			this.pic4.Location = new System.Drawing.Point(328, 79);
			this.pic4.Name = "pic4";
			this.pic4.Size = new System.Drawing.Size(100, 63);
			this.pic4.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
			this.pic4.TabIndex = 5;
			this.pic4.TabStop = false;
			this.pic4.Click += new System.EventHandler(this.pic4_Click);
			// 
			// pic3
			// 
			this.pic3.Cursor = System.Windows.Forms.Cursors.Hand;
			this.pic3.Image = ((System.Drawing.Image)(resources.GetObject("pic3.Image")));
			this.pic3.Location = new System.Drawing.Point(222, 79);
			this.pic3.Name = "pic3";
			this.pic3.Size = new System.Drawing.Size(100, 63);
			this.pic3.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
			this.pic3.TabIndex = 4;
			this.pic3.TabStop = false;
			this.pic3.Click += new System.EventHandler(this.pic3_Click);
			// 
			// pic2
			// 
			this.pic2.Cursor = System.Windows.Forms.Cursors.Hand;
			this.pic2.Image = ((System.Drawing.Image)(resources.GetObject("pic2.Image")));
			this.pic2.Location = new System.Drawing.Point(116, 79);
			this.pic2.Name = "pic2";
			this.pic2.Size = new System.Drawing.Size(100, 63);
			this.pic2.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
			this.pic2.TabIndex = 3;
			this.pic2.TabStop = false;
			this.pic2.Click += new System.EventHandler(this.pic2_Click);
			// 
			// pic1
			// 
			this.pic1.Cursor = System.Windows.Forms.Cursors.Hand;
			this.pic1.Image = global::LVClient.Properties.Resources.ImageLoading;
			this.pic1.Location = new System.Drawing.Point(10, 79);
			this.pic1.Name = "pic1";
			this.pic1.Size = new System.Drawing.Size(100, 63);
			this.pic1.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
			this.pic1.TabIndex = 2;
			this.pic1.TabStop = false;
			this.pic1.Click += new System.EventHandler(this.pic1_Click);
			// 
			// picSamplePic
			// 
			this.picSamplePic.Image = global::LVClient.Properties.Resources.VerifyCodexxx1;
			this.picSamplePic.Location = new System.Drawing.Point(87, -2);
			this.picSamplePic.Name = "picSamplePic";
			this.picSamplePic.Size = new System.Drawing.Size(261, 66);
			this.picSamplePic.SizeMode = System.Windows.Forms.PictureBoxSizeMode.CenterImage;
			this.picSamplePic.TabIndex = 0;
			this.picSamplePic.TabStop = false;
			// 
			// timer1
			// 
			this.timer1.Tick += new System.EventHandler(this.timer1_Tick);
			// 
			// frmImageCheck
			// 
			this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
			this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
			this.ClientSize = new System.Drawing.Size(442, 150);
			this.Controls.Add(this.pic4);
			this.Controls.Add(this.pic3);
			this.Controls.Add(this.pic2);
			this.Controls.Add(this.pic1);
			this.Controls.Add(this.picSamplePic);
			this.Name = "frmImageCheck";
			this.Text = "Chon hinh khong co";
			this.Load += new System.EventHandler(this.frmImageCheck_Load);
			this.FormClosed += new System.Windows.Forms.FormClosedEventHandler(this.frmImageCheck_FormClosed);
			((System.ComponentModel.ISupportInitialize)(this.pic4)).EndInit();
			((System.ComponentModel.ISupportInitialize)(this.pic3)).EndInit();
			((System.ComponentModel.ISupportInitialize)(this.pic2)).EndInit();
			((System.ComponentModel.ISupportInitialize)(this.pic1)).EndInit();
			((System.ComponentModel.ISupportInitialize)(this.picSamplePic)).EndInit();
			this.ResumeLayout(false);

		}

		#endregion

		public System.Windows.Forms.PictureBox picSamplePic;
		public System.Windows.Forms.PictureBox pic1;
		public System.Windows.Forms.PictureBox pic2;
		public System.Windows.Forms.PictureBox pic3;
		public System.Windows.Forms.PictureBox pic4;
		private System.Windows.Forms.Timer timer1;

	}
}